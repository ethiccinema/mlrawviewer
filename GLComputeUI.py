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
import numpy as np

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

class SharedVbo(object):
    def __init__(self,**kwds):
        super(SharedVbo,self).__init__(**kwds)
        self.data = np.zeros(shape=(1024*16,),dtype=np.float32)
        self.vbo = vbo.VBO(self.data)
        self.bound = False
        self.avail = 1024*64
        self.allocated = 0
    def bind(self):
        self.vbo.bind()
        self.bound = True
    def allocate(self,amount):
        if (self.avail-amount)>0:
            offset = self.allocated
            self.allocated += amount
            self.avail -= amount
            return offset 
        return None
    def update(self,data,offset):
        ow = offset/4
        self.vbo[ow:(ow+len(data))] = data
    def vboOffset(self,offset):
        return self.vbo + offset        
    def upload(self):
        self.vbo.copy_data()

class Timeline(object):
    def __init__(self,**kwds):
        super(Timeline,self).__init__(**kwds)
        self.now = 0.0
        self.start = 0.0
    def setNow(self,now):
        self.now = now
    def time(self):
        return self.now - self.start

def clip(val,low,high):
    if val<low: return low
    elif val>high: return high
    else: return val
 
class Animation(object):
    LINEAR = 0
    SMOOTH = 1
    def __init__(self,timeline,initval=0.0,**kwds):
        super(Animation,self).__init__(**kwds)
        self.timeline = timeline
        self.oldval = initval
        self.targval = initval
        self.tstart = 0.0
        self.tend = 0.0
        self.duration = 0.0
        self.delta = 0.0
        self.interp = self.LINEAR
    def setTarget(self,target,duration,delay=0.0,interp=LINEAR):
        self.oldval = self.targval
        self.targval = target
        self.tstart = self.timeline.time() + delay
        self.tend = self.tstart + duration
        self.duration = duration
        self.delta = self.targval - self.oldval
        self.interp = interp
    def progress(self):
        """ Return animation progress from 0.0 to 1.0 """
        t = self.timeline.time()
        #before = clip((self.tend-t)/dur,0.0,1.0)
        if self.duration <= 0.0: return 1.0
        return clip((t-self.tstart)/self.duration,0.0,1.0)
    def value(self):
        p = self.progress()
        if self.interp == self.LINEAR:
            return self.oldval + self.delta*p
        elif self.interp == self.SMOOTH: # Standard smoothstep function
            return self.oldval + self.delta*p*p*(3.0 - 2.0*p)
 
class Drawable(object):
    def __init__(self,**kwds):
        super(Drawable,self).__init__(**kwds)
        self.ignoreInput = True
        self.motionWhileClicked = False
    def render(self,scene,matrix):
        pass
    def input2d(self,matrix,x,y,buttons):
        return None # Not handled

class Scene(object):
    def __init__(self,size=(0,0)):
        self.drawables = []
        self.size = size
        self.matrix = Matrix4x4()
        self.inputMatrix = Matrix4x4()
        self.eventHandler = None
        self.ignoreMotion = True
        self.setPosition(0.0, 0.0)
    def setSize(self,w,h):
        self.size = (float(w),float(h))
        self.updateMatrices()
    def setPosition(self,x,y):
        self.position = (float(x), float(y))
        self.updateMatrices()
    def updateMatrices(self):
        self.matrix.identity()
        self.matrix.viewport(*self.size)
        self.matrix.translate(-self.size[0]*0.5,-self.size[1]*0.5)
        self.inputMatrix.identity()
        self.inputMatrix.translate(self.position[0],self.position[1])
    def setTarget(self):
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        glViewport(int(self.position[0]),int(self.position[1]),int(self.size[0]),int(self.size[1]))
    def render(self):
        self.setTarget()
        for d in self.drawables:
            d.render(self,self.matrix)
        self.renderComplete()
    def prepareToRender(self):
        pass
    def renderComplete(self):
        pass
    def input2d(self,x,y,buttons):
        if self.eventHandler == None: 
            if self.ignoreMotion:
                ignore = True
                for b in buttons:
                    if b==GLCompute.GLCompute.BUTTON_DOWN:
                        ignore = False
                if ignore:
                    return None
            #if buttons[0]==0 and buttons[1]==0: return None
            for d in self.drawables:
                if d.ignoreInput: continue
                self.eventHandler = d.input2d(self.inputMatrix,x,y,buttons)
                if self.eventHandler != None: break
            return self.eventHandler
        else:
            if self.eventHandler.motionWhileClicked or (buttons[0]==0 and buttons[1]==0):
                self.eventHandler = self.eventHandler.input2d(self.inputMatrix,x,y,buttons)

class Geometry(Drawable):
    def __init__(self,svbo,**kwds):
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
        self.opacity = 1.0
        self.edges = (1.0,1.0,0.0,0.0)
        self.svbo = svbo
        self.svbobase = None
        self.svbospace = None
        self.vab = None
        self.texture = None
    def reserve(self,space):
        self.svbobase = self.svbo.allocate(space) 
        #print "reserved",self.svbobase,space
        if self.svbobase != None:
            self.svbospace = space
    def setTransformOffset(self,x,y):
        self.transformOffset = (x,y)
    def setPos(self,x,y):
        self.pos = (x,y)    
    def setScale(self,scale):
        self.scale = scale    
    def setVab(self,vertices):
        #print "setVab",len(vertices),self.svbobase,self.svbospace,vertices.size,vertices
        if (vertices.size)<=self.svbospace:
            self.svbo.update(vertices,self.svbobase)
            self.vab = (self.svbo.vboOffset(self.svbobase),self.svbo.vboOffset(self.svbobase+16),self.svbo.vboOffset(self.svbobase+32),len(vertices)/12)
    def rectangle(self,*args,**kwargs):
        if self.svbobase == None:
            self.reserve(6*12*4)
        texture,vertices = self.shader.rectangle(*args,**kwargs)
        self.setVab(vertices)
        self.texture = texture
    def gradient(self,*args,**kwargs):
        if self.svbobase == None:
            self.reserve(6*12*4)
        texture,vertices = self.shader.gradient(*args,**kwargs)
        self.setVab(vertices)
        self.texture = texture
    def label(self,*args,**kwargs):
        if self.svbobase == None:
            chars = len(args[0])+10
            #print "chars in",args[0],chars
            self.reserve(6*12*4*chars)
        texture,vertices = self.shader.label(*args,**kwargs)
        #print vertices
        self.setVab(vertices)
        self.texture = texture
    def render(self,scene,matrix):
        if self.vab != None and self.opacity>0.0:
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
            self.shader.draw(self.vab,self.texture,self.matrix,self.colour,self.opacity,self.edges)
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
        #print lx,ly,self.size[0],self.size[1]
        if lx>=0.0 and lx<=(self.size[0]) and ly>=0.0 and ly<=(self.size[1]):
            return self.event2d(lx,ly,buttons)
        else:
            return None # Not handled
    def event2d(self,lx,ly,buttons):
        """
        A 2d event ocurred in our active region    
        """
        return None

class Button(Geometry):
    def __init__(self,width,height,onclick,**kwds):
        super(Button,self).__init__(**kwds)
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
            return self
        else:
            self.notClicked = True
        return None

class XYGraph(Button):
    def __init__(self,width,height,onclick,**kwds):
        super(XYGraph,self).__init__(width,height,onclick,**kwds)
        self.motionWhileClicked = True
    def event2d(self,lx,ly,buttons):
        if buttons[0] == 1:
            # Clicked
            self.onclick(lx,ly)
            return self
        return None
        
