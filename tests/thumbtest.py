#!/usr/bin/python2.7


# standard python imports. Should not be missing
import sys,struct,os,math,time,datetime

# So we can use modules from the main dir
root = os.path.split(sys.path[0])[0]
sys.path.append(root)

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
import PerformanceLog
from PerformanceLog import PLOG
PerformanceLog.PLOG_CONTROL(False)
PLOG_FILE_IO = PerformanceLog.PLOG_TYPE(0,"FILE_IO")
PLOG_FRAME = PerformanceLog.PLOG_TYPE(1,"FRAME")
PLOG_CPU = PerformanceLog.PLOG_TYPE(2,"CPU")
PLOG_GPU = PerformanceLog.PLOG_TYPE(3,"GPU")


import GLCompute
import GLComputeUI as ui
import Font
from ShaderText import *
from Matrix import *
import MlRaw

class Viewer(GLCompute.GLCompute):
    def __init__(self,path,**kwds):
        super(Viewer,self).__init__(width=960,height=540,**kwds)
        self._init = False
        self.path = path
        self.files = os.listdir(self.path)
        self.thumbs = []
    def onIdle(self):
        PLOG(PLOG_FRAME,"onIdle start")
        if not self._init: 
            self.redisplay()
        raw = None
        while raw==None and len(self.files)>0:
            nextfile = self.files.pop()
            try:
                raw = MlRaw.loadRAWorMLV(os.path.join(self.path,nextfile),preindex=False)
                if (raw != None):
                    PLOG(PLOG_FRAME,"opened raw file %s"%nextfile)
                    thumbData = raw.firstFrame.thumb()
                    PLOG(PLOG_FRAME,"add to atlas")
                    thumbIndex = self.atlas.atlasadd(thumbData.flatten(),thumbData.shape[1],thumbData.shape[0])
                    PLOG(PLOG_FRAME,"added to atlas")
                    uv = self.atlas.atlas[thumbIndex]
                    texture,vertices = self.shader.rectangle(thumbData.shape[1],thumbData.shape[0],uv=uv,solid=0.0,tex=0.5,tint=0.0)
                    svbobase = self.svbo.allocate(6*12*4)
                    vab = (self.svbo.vboOffset(svbobase),self.svbo.vboOffset(svbobase+16),self.svbo.vboOffset(svbobase+32),len(vertices)/12)
                    self.svbo.upload()
                    self.thumbs.append(vab)
                    print "Thumbnail added"
            except:
                pass
        self.redisplay()
        PLOG(PLOG_FRAME,"onIdle ends")
    def windowName(self):
        return "Thumbnail test"
    def init(self):
        if self._init: return
        self.atlas = GLCompute.Texture((1024,1024),rgbadata=np.zeros(shape=(1024,1024,3),dtype=np.uint16),hasalpha=False,mono=False,sixteen=True,mipmap=False)
        self.shader = ShaderText(None)
        self.matrix = Matrix4x4()
        self.svbo = ui.SharedVbo()
        self.svbo.bind()
        #self.raw.firstFrame.demosaic()
        self._init = True
    def onDraw(self,width,height):
        PLOG(PLOG_FRAME,"onDraw start")
        self.init()
        y = 0 #height/2.0-170.0
        x = 0 # width/2.0
        for t in self.thumbs:
            self.matrix.identity()
            self.matrix.viewport(width,height)
            self.matrix.translate(x,y)
            x += 0.1 # 260.0
            if x>(width/2.0-260.0):
                x = 0 # -width/2.0 
                y += 0.1 #170.0
            self.shader.draw(t,self.atlas,self.matrix)
        PLOG(PLOG_FRAME,"onDraw end")

def main(): 
    rmc = Viewer(sys.argv[1])   
    ret = rmc.run()
    PerformanceLog.PLOG_PRINT()
    return ret

if __name__ == '__main__':
    sys.exit(main())
