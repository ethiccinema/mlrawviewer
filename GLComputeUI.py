"""
GLComputeUI.py
(c) Andrew Baldwin 2014

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

This is a simple framework for doing (graphics) 
computation and display using OpenGL FBOs

"""

# standard python imports. Should not be missing
import sys,time,os,os.path

# Our modules
from Matrix import *
import GLCompute
from ShaderText import *
import Font

# OpenGL. Could be missing
try:
    from OpenGL.GL import *
    from OpenGL.arrays import vbo
    from OpenGL.GL.shaders import compileShader, compileProgram
    from OpenGL.GL.framebufferobjects import *
    from OpenGL.GL.ARB.texture_rg import *
    from OpenGL.GL.EXT.framebuffer_object import *
except Exception,err:
    print """There is a problem with your python environment.
I Could not import the pyOpenGL module.
On Debian/Ubuntu try "sudo apt-get install python-opengl"
"""
    sys.exit(1)
FONT = Font.Font(os.path.join(os.path.split(__file__)[0],"data/os.glf"))


shaders = {}

class Drawable(object):
    def __init__(self,**kwds):
        super(Drawable,self).__init__(**kwds)
        self.ignoreInput = True
    def render(self,scene,matrix):
        pass
    def input2d(self,matrix,x,y,buttons):
        return False # Not handled

class Scene(object):
    def __init__(self,size=(0,0)):
        self.drawables = []
        self.size = size
        self.position = (0, 0)
        self.matrix = Matrix4x4()
    def setTarget(self):
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        glViewport(self.position[0],self.position[1],self.size[0],self.size[1])
    def render(self,frame):
        self.frame = frame
        self.prepareToRender()
        self.setTarget()
        self.matrix.identity()
        self.matrix.viewport(*self.size)
        self.matrix.translate(-self.size[0]*0.5,-self.size[1]*0.5)
        for d in self.drawables:
            d.render(self,self.matrix)
        self.renderComplete()
    def prepareToRender(self):
        pass
    def renderComplete(self):
        pass
    def input2d(self,x,y,buttons):
        self.matrix.identity()
        #self.matrix.viewport(*self.size)
        #self.matrix.translate(-self.size[0]*0.5,-self.size[1]*0.5)
        handled = False
        for d in self.drawables:
            if d.ignoreInput: continue
            handled = d.input2d(self.matrix,x,y,buttons)
            if handled: break
        return handled

class Geometry(Drawable):
    def __init__(self,**kwds):
        super(Geometry,self).__init__(**kwds)
        global shaders
        self.shader = shaders.setdefault("text",ShaderText(FONT))
        self.geometry = None
        self.matrix = Matrix4x4()
        self.colour = (1.0,1.0,1.0,1.0)
        self.pos = (0.0,0.0)
        self.transformOffset = (0.0,0.0)
        self.scale = 1.0
        self.rotation = 0.0
        self.children = []
        self.size = (0,0)
    def setTransformOffset(self,x,y):
        self.transformOffset = (x,y)
    def setPos(self,x,y):
        self.pos = (x,y)    
    def setScale(self,scale):
        self.scale = scale    
    def rectangle(self,*args,**kwargs):
        self.geometry = self.shader.rectangle(*args,**kwargs)
    def label(self,*args,**kwargs):
        self.geometry = self.shader.label(*args,**kwargs)
    def render(self,scene,matrix):
        if self.geometry:
            # Update matrix
            self.matrix.identity()
            self.matrix.translate(self.pos[0],self.pos[1])
            if self.rotation != 0.0:
                self.matrix.rotation(2.0*3.1415927*self.rotation/360.0)    
            self.matrix.translate(-self.transformOffset[0],-self.transformOffset[1])
            if self.scale != 1.0:
                self.matrix.scale(self.scale)
            #if self.rotation != 0.0:
            #    self.matrix.rotation(2.0*3.1415927*self.rotation/360.0)    
            self.matrix.mult(matrix);
            self.shader.draw(self.geometry,self.matrix,self.colour)
        for c in self.children:
            c.render(scene,self.matrix) # Relative to parent
    def input2d(self,matrix,x,y,buttons):
        # Update matrix
        self.matrix.identity()
        self.matrix.translate(self.pos[0],self.pos[1])
        if self.rotation != 0.0:
            self.matrix.rotation(2.0*3.1415927*self.rotation/360.0)    
        self.matrix.translate(-self.transformOffset[0],-self.transformOffset[1])
        if self.scale != 1.0:
            self.matrix.scale(self.scale)
        self.matrix.mult(matrix);
        # Transform the scene coords into object space
        lx,ly,lz = self.matrix.multveci(x,y)
        if lx>=0.0 and lx<=(self.size[0]) and ly>=0.0 and ly<=(self.size[1]):
            return self.event2d(lx,ly,buttons)
        else:
            return False # Not handled
    def event2d(self,lx,ly,buttons):
        """
        A 2d event ocurred in our active region    
        """
        return False

class Button(Geometry):
    def __init__(self,width,height,onclick,**kwds):
        super(Button,self).__init__(**kwds)
        print self.geometry
        self.size = (width,height)
        self.ignoreInput = False
        self.onclick = onclick
        self.notClicked = True
    def event2d(self,lx,ly,buttons):
        if buttons[0] == 1:
            # Clicked
            if self.notClicked:
                self.onclick(lx,ly)
                self.notClicked = False            
            return True
        else:
            self.notClicked = True
        return False
        
