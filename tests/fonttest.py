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
import GLCompute
import Font
from ShaderText import *
from Matrix import *

class Viewer(GLCompute.GLCompute):
    def __init__(self,**kwds):
        super(Viewer,self).__init__(width=960,height=540,**kwds)
        self._init = False
        self.font = Font.Font(os.path.join(root,"data/os.glf"))
        self.time = time.time()
    def onIdle(self):
        self.redisplay()
    def windowName(self):
        return "GLF font test"
    def benchmark(self):
        start = time.time()
        for i in range(100):
            label = self.shader.label(self.font,"this is a test. The quick brown fox jumped over the lazy dog!") 
        end = time.time()
        print "100 labels took",end-start,100.0/(end-start)
    def init(self):
        if self._init: return
        self.fonttex = GLCompute.Texture((1024,1024),rgbadata=self.font.atlas,hasalpha=False,mono=True,sixteen=False,mipmap=True)
        self.shader = ShaderText(self.font)
        self.matrix = Matrix4x4()
        self.benchmark()
        self._init = True
    def onDraw(self,width,height):
        # First convert Raw to RGB image at same size
        self.init()
        self.rotmat = Matrix4x4()
        dt = datetime.datetime.now()
        timestamp = self.shader.label(self.font,"%02d:%02d:%02d.%02d"%(dt.hour,dt.minute,dt.second,dt.microsecond*0.0001)) 
        for i in range(20):
            self.matrix.identity()
            self.matrix.viewport(width,height)
            self.matrix.scale(64.0*(1.0/(64.0*width)))
            self.matrix.translate(-float(width)/2.0+i*float(width)/20.0,-float(height)/2.0+i*float(height)/20.0)
            self.shader.draw(timestamp,self.matrix,(float(i)/20.0,1.0-float(i)/20.0,1.0,1.0))

def main(): 
    rmc = Viewer()   
    return rmc.run()

if __name__ == '__main__':
    sys.exit(main())
