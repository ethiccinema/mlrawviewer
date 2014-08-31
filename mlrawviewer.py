#!/usr/bin/python2.7
"""
mlrawviewer.py
(c) Andrew Baldwin 2013-2014

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
of the Software, and to permit persons to whom the Software is furnished to do
so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

# standard python imports. Should not be missing
import sys,struct,os,math,time,datetime,subprocess,signal,threading,Queue,wave,zlib,array
from threading import Thread

import dialogs

import multiprocessing
import multiprocessing.queues
from multiprocessing import Process

from Config import config

programpath = os.path.abspath(os.path.split(sys.argv[0])[0])
if getattr(sys,'frozen',False):
    programpath = sys._MEIPASS
    # Assume we have no console, so try to redirect output to a log file...somewhere
    try:
        sys.stdout = file(config.logFilePath(),"a")
        sys.stderr = sys.stdout
    except:
        pass

import LUT

print "MlRawViewer v"+config.versionString()
print "(c) Andrew Baldwin & contributors 2013-2014"

# OpenGL. Could be missing
try:
    import OpenGL
    #OpenGL.ERROR_CHECKING = False # Only for one erroneously-failing Framebuffer2DEXT call on Windows with Intel...grrr
    from OpenGL.GL import *
    from OpenGL.GL.framebufferobjects import *
except Exception,err:
    print """There is a problem with your python environment.
I Could not import the pyOpenGL module.
On Debian/Ubuntu try "sudo apt-get install python-opengl"
"""
    sys.exit(1)

# numpy. Could be missing
try:
    import numpy as np
except Exception,err:
    print """There is a problem with your python environment.
I Could not import the numpy module.
On Debian/Ubuntu try "sudo apt-get install python-numpy"
"""
    sys.exit(1)

import MlRaw
from Viewer import *

def main():
    filename = None
    if len(sys.argv)<2:
        #print "Error. Please specify an MLV or RAW file to view"
        #return -1
        directory = config.getState("directory")
        if directory == None:
            directory = '~'
        afile = openFilename(directory)
        if afile != None:
            filename = afile
            if afile != '':
                config.setState("directory",os.path.dirname(filename))
    if filename == None:
        filename = sys.argv[1].decode(sys.getfilesystemencoding())
    if not os.path.exists(filename):
        print "Error. Specified filename",filename,"does not exist"
        return -1

    # Try to pick a sensible default filename for any possible encoding

    outfilename = config.getState("targetDir") # Restore persisted target
    if outfilename == None:
        outfilename = os.path.split(filename)[0]
    poswavname = os.path.splitext(filename)[0]+".WAV"
    if os.path.isdir(filename):
        wavdir = filename
    else:
        wavdir = os.path.split(filename)[0]
    wavnames = [w for w in os.listdir(wavdir) if w.lower().endswith(".wav")]
    #print "wavnames",wavnames
    if os.path.isdir(filename) and len(wavnames)>0:
        wavfilename = os.path.join(wavdir,wavnames[0])
    else:
        wavfilename = poswavname # Expect this to be extracted by indexing of MLV with SND

    #print "wavfilename",wavfilename
    if len(sys.argv)==3:
        # Second arg could be WAV or outfilename
        if sys.argv[2].lower().endswith(".wav"):
            wavfilename = sys.argv[2]
        else:
            outfilename = sys.argv[2]
            config.setState("targetDir",outfilename)
    elif len(sys.argv)>3:
        wavfilename = sys.argv[2]
        outfilename = sys.argv[3]
        config.setState("targetDir",outfilename)

    try:
        r = MlRaw.loadRAWorMLV(filename)
        if r==None:
            sys.stderr.write("%s not a recognised RAW/MLV file or CinemaDNG directory.\n"%filename)
            return 1
    except Exception, err:
        import traceback
        traceback.print_exc()
        sys.stderr.write('Could not open file %s. Error:%s\n'%(filename,str(err)))
        return 1


    rmc = Viewer(r,outfilename,wavfilename)
    ret = rmc.run()
    PerformanceLog.PLOG_PRINT()
    return ret


if __name__ == '__main__':
    sys.exit(main())
