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
import GLComputeUI as ui
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
        return "UI test"
    def init(self):
        if self._init: return
        self.fonttex = GLCompute.Texture((1024,1024),rgbadata=self.font.atlas,hasalpha=False,mono=True,sixteen=False,mipmap=True)
        self.shader = ShaderText(self.font)
        self.matrix = Matrix4x4()
        self.pos = (0.0,0.0)
        self.left = 0.0
        self.right = 0.0
        self.box = self.shader.rectangle(100,100,rgba=(1.0,1.0,1.0,1.0))
        self._init = True
    def onDraw(self,width,height):
        self.init()
        self.matrix.identity()
        self.matrix.viewport(width,height)
        self.matrix.translate(-width/2+self.pos[0],height/2-self.pos[1])
        self.shader.draw(self.box,self.matrix,(self.left,self.right,1.0,1.0))
    def input2d(self,x,y,buttons):
        print "input2d",x,y,buttons
        self.pos = (x,y)
        if buttons[self.BUTTON_LEFT]==self.BUTTON_DOWN: self.left = 1.0
        else: self.left = 0.0
        if buttons[self.BUTTON_RIGHT]==self.BUTTON_DOWN: self.right = 1.0
        else: self.right = 0.0
    
    


def main(): 
    rmc = Viewer()   
    return rmc.run()

if __name__ == '__main__':
    sys.exit(main())
