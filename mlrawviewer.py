#!/usr/bin/python2
"""
mlrawviewer.py
(c) Andrew Baldwin 2013

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
import sys,struct,os,math,time

# OpenGL. Could be missing
try:
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

# Now import our own modules
import GLCompute
import MlRaw
from ShaderDemosaicNearest import *
from ShaderDemosaicBilinear import *
from ShaderDisplaySimpleToneMap import *

class Viewer(GLCompute.GLCompute):
    def __init__(self,raw,**kwds):
        super(Viewer,self).__init__(width=960,height=540,**kwds)
        self._init = False
        self._raw = raw
        self.time = 0
    def windowName(self):
        return "MLRAW Viewer"
    def init(self):
        if self._init: return
        self.shader = ShaderDemosaicBilinear()
        #self.shader = ShaderDemosaicNearest()
        print "Using",self.shader.demosaic_type,"demosaic algorithm"
        self._raw.preloadFrame(0)
        frame0 = self._raw.frame(0)
        frame0.convert()
        print "Width:",self._raw.width(),"Height:",self._raw.height(),"Frames:",self._raw.frames()
        self.rawUploadTex = GLCompute.Texture((self._raw.width(),self._raw.height()),rgbadata=frame0.rawimage,hasalpha=False,mono=True,sixteen=True)
        self.rgbImage = GLCompute.Texture((self._raw.width(),self._raw.height()),None,hasalpha=False,mono=False,sixteen=True)
        self.displayShader = ShaderDisplaySimpleToneMap()
        self._raw.preloadFrame(0)
        self._init = True
    def onDraw(self,width,height):
        # First convert Raw to RGB image at same size
        self.init()
        self.rgbImage.bindfbo()
        frameNumber = int((1*self._frames)/1 % self._raw.frames())
        frame = self._raw.frame(frameNumber)
        nextFrame = int((1*(self._frames+1)) % self._raw.frames())
        self._raw.preloadFrame(nextFrame)
        if (frame):
            frame.convert()
            self.rawUploadTex.update(frame.rawimage)
            self.shader.demosaicPass(self.rawUploadTex,frame.black)
        # else missing frame, show the previous frame again

        # Now display the RGB image
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        glViewport(0,0,width,height)
        brightness = 50.0
        balance = (2.0*brightness,1.0*brightness,1.5*brightness)
        self.displayShader.draw(self.rgbImage,balance)

        #self.time += 0.001
        # FPS calculations
        if self._frames%30==0:
            dur = time.time()-self._start
            self._start = time.time()
            if self._frames>0:
                print "FPS:",30.0/float(dur)
       
def main(): 
    filename = sys.argv[1]
    try:
        r = MlRaw.loadRAWorMLV(filename)
    except Exception, err:
        sys.stderr.write('Could not open file %s. Error:%s\n'%(filename,str(err)))
        return 1
    rmc = Viewer(r)   
    return rmc.run()
    return 0

if __name__ == '__main__':
    sys.exit(main())
