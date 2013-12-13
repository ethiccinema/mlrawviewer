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
import sys,struct,os,math,time,datetime

version = "1.0.1"

print "MlRawViewer v"+version
print "(c) Andrew Baldwin & contributors 2013"


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
import Font
from Matrix import *
from ShaderDemosaicNearest import *
from ShaderDemosaicBilinear import *
from ShaderDisplaySimpleToneMap import *
from ShaderText import *

class Demosaicer(GLCompute.Drawable):
    def __init__(self,raw,uploadTex,**kwds):
        super(Demosaicer,self).__init__(**kwds)
        self.shader = ShaderDemosaicBilinear()
        self.raw = raw
        self.rawUploadTex = uploadTex
    def render(self,scene):
        f = scene.frame
        frame = f 
        frameNumber = int((1*frame)/1 % self.raw.frames())
        frameData = self.raw.frame(frameNumber)
        nextFrame = int((1*(frame+1)) % self.raw.frames())
        self.raw.preloadFrame(nextFrame)
        if (frameData):
            frameData.convert()
            self.rawUploadTex.update(frameData.rawimage)
            self.shader.demosaicPass(self.rawUploadTex,frameData.black)

class DemosaicScene(GLCompute.Scene):
    def __init__(self,raw,**kwds):
        super(DemosaicScene,self).__init__(**kwds)
        f = 0
        self.raw = raw
        self.raw.preloadFrame(f)
        frame0 = self.raw.frame(f)
        frame0.convert()
        self.raw.preloadFrame(f)
        print "Width:",self.raw.width(),"Height:",self.raw.height(),"Frames:",self.raw.frames()
        self.rawUploadTex = GLCompute.Texture((self.raw.width(),self.raw.height()),rgbadata=frame0.rawimage,hasalpha=False,mono=True,sixteen=True)
        self.rgbImage = GLCompute.Texture((self.raw.width(),self.raw.height()),None,hasalpha=False,mono=False,sixteen=True)
        demosaicer = Demosaicer(raw,self.rawUploadTex)
        print "Using",demosaicer.shader.demosaic_type,"demosaic algorithm"
        self.drawables.append(demosaicer)
    def setTarget(self):
        self.rgbImage.bindfbo()

class Display(GLCompute.Drawable):
    def __init__(self,rgbImage,**kwds):
        super(Display,self).__init__(**kwds)
        self.displayShader = ShaderDisplaySimpleToneMap()
        self.rgbImage = rgbImage
    def render(self,scene):
        # Now display the RGB image
        #self.rgbImage.addmipmap()
        brightness = 50.0
        balance = (2.0*brightness,1.0*brightness,1.5*brightness)
        # Scale
        self.displayShader.draw(scene.size[0],scene.size[1],self.rgbImage,balance)
        # 1 to 1
        # self.displayShader.draw(self.rgbImage.width,self.rgbImage.height,self.rgbImage,balance)

class Geometry(GLCompute.Drawable):
    def __init__(self,shader,**kwds):
        super(Geometry,self).__init__(**kwds)
        self.textshader = shader
        self.geometry = None
        self.matrix = Matrix4x4()
        self.colour = (1.0,1.0,1.0,1.0)
    def render(self,scene):
        if self.geometry:
            self.textshader.draw(self.geometry,self.matrix,self.colour)

class DisplayScene(GLCompute.Scene):
    def __init__(self,raw,rgbImage,font,**kwds):
        super(DisplayScene,self).__init__(**kwds)
        self.raw = raw
        self.textshader = ShaderText(font)
        self.rgbImage = rgbImage
        self.display = Display(rgbImage)
        self.progressBackground = Geometry(shader=self.textshader)
        self.progress = Geometry(shader=self.textshader)
        self.timestamp = Geometry(shader=self.textshader)
        self.drawables.extend([self.display,self.progressBackground,self.progress,self.timestamp])
    def prepareToRender(self):
        f = self.frame
        frameNumber = int(f % self.raw.frames())
        m2 = Matrix4x4()
        width,height = self.size
        m2.viewport(width,height)
        m2.translate(7.-float(width)/2.0,7.-float(height)/2.0)
        rectHeight = 0.08/(float(width)/540.0)
        rectWidth = 1.9
        self.progressBackground.geometry = self.textshader.rectangle(rectWidth,rectHeight,rgba=(0.2,0.2,0.2,0.2),update=self.progressBackground.geometry)
        self.progress.geometry = self.textshader.rectangle((float(frameNumber)/float(self.raw.frames()))*rectWidth,rectHeight,rgba=(1.0,1.0,0.2,0.2),update=self.progress.geometry)
        self.progressBackground.matrix = m2
        self.progress.matrix = m2
        m = Matrix4x4()
        m.viewport(width,height)
        m.scale(40.0*(1.0/(64.0*float(height)*(float(width)/float(height)))))
        m.translate(10.-float(width)/2.0,10.-float(height)/2.0)
        self.timestamp.matrix = m
        minutes = (frameNumber/25)/60
        seconds = (frameNumber/25)%60
        frames = frameNumber%25
        self.timestamp.geometry = self.textshader.label(self.textshader.font,"%02d:%02d.%02d"%(minutes,seconds,frames),update=self.timestamp.geometry)
        self.timestamp.colour = (0.1,0.1,0.2,1.0)

class Viewer(GLCompute.GLCompute):
    def __init__(self,raw,**kwds):
        userWidth = 720
        self.vidAspect = float(raw.height())/(raw.width())
        super(Viewer,self).__init__(width=userWidth,height=int(userWidth*self.vidAspect),**kwds)
        self._init = False
        self._raw = raw
        self.font = Font.Font("data/os.glf")
        self.time = 0
        self._fps = 25 # TODO - This should be read from the file
        self.paused = False
        self.needsRefresh = False
    def windowName(self):
        return "MlRawViewer v"+version+" - "+os.path.split(sys.argv[1])[1]
    def init(self):
        if self._init: return
        self.demosaic = DemosaicScene(self._raw,size=(self._raw.width(),self._raw.height()))
        self.scenes.append(self.demosaic)
        self.display = DisplayScene(self._raw,self.demosaic.rgbImage,self.font,size=(0,0))
        self.scenes.append(self.display)
        self.rgbImage = self.demosaic.rgbImage
        self._init = True
    def onDraw(self,width,height):
        # First convert Raw to RGB image at same size
        self.init()
        self.display.size = (width,height)
        self.renderScenes()
    def jump(self,framesToJumpBy):
        self._frames += framesToJumpBy
        self.refresh()
    def key(self,k,x,y):
        if ord(k)==32:
            self.paused = not self.paused
        elif k=='.': # Nudge forward one frame - best when paused
            self.jump(0) # If paused, will automatically load next frame
        elif k==',': # Nudge back on frame - best when paused
            self.jump(-2) # If paused, will automatically be on next frame, so need to go back 2!
        else:
            super(Viewer,self).key(k,x,y)
    def specialkey(self,k,x,y):
        #print "special key",k
        if k==100: # Left cursor
            self.jump(-self._fps) # Go back 1 second (will wrap)
        elif k==102: # Right cursor
            self.jump(self._fps) # Go forward 1 second (will wrap)
        else:
            super(Viewer,self).specialkey(k,x,y)
    def onIdle(self):
        if self.needsRefresh and self.paused:
            self.redisplay()

        now = GLCompute.timeInUsec()
        if not self.needsRefresh and not self.paused and (now-self._last >= (1.0/self._fps)):
            #print now,self._last,1.0/self._fps
            self.redisplay()

        self.needsRefresh = False

    def refresh(self):
        self.needsRefresh = True 

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
