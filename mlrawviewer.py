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
    rmc = Viewer()
    if len(sys.argv)>1:
        rmc.load(sys.argv[1])
    else:
        rmc.openBrowser()
    ret = rmc.run()
    PerformanceLog.PLOG_PRINT()
    return ret

if __name__ == '__main__':
    sys.exit(main())
