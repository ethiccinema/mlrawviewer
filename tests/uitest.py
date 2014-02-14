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
        self.scene = ui.Scene()
        self.scenes.append(self.scene)
        self.box = ui.Geometry()
        self.box.rectangle(100,100,rgba=(1.0,1.0,1.0,1.0))
        self.childbox = ui.Geometry()
        self.childbox.rectangle(50,50,rgba=(1.0,1.0,1.0,1.0))
        self.childbox.colour = (0.0,1.0,0.0,0.5)
        self.childbox.setTransformOffset(25.0,25.0)
        self.childbox.setPos(50.0,50.0)
        self.hw = ui.Geometry()
        self.hw.label("Hello World!")
        self.hw.setScale(1.0)
        self.childbox.children.append(self.hw)
        self.box.children.append(self.childbox)
        self.scene.drawables.append(self.box)
        self._init = True
    def onDraw(self,width,height):
        self.init()
        self.box.colour = (self.left,self.right,1.0,1.0)
        self.scene.size = (width,height)
        self.childbox.rotation += 1.0
        self.box.rotation -= 0.5
        self.renderScenes()
    def input2d(self,x,y,buttons):
        print "input2d",x,y,buttons
        self.box.setPos(x,y)
        if buttons[self.BUTTON_LEFT]==self.BUTTON_DOWN: self.left = 1.0
        else: self.left = 0.0
        if buttons[self.BUTTON_RIGHT]==self.BUTTON_DOWN: self.right = 1.0
        else: self.right = 0.0
        self.box.setScale(1.0+self.left+self.right)

def main(): 
    rmc = Viewer()   
    return rmc.run()

if __name__ == '__main__':
    sys.exit(main())
