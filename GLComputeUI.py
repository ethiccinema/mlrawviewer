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

import PerformanceLog
from PerformanceLog import PLOG
PLOG_FILE_IO = PerformanceLog.PLOG_TYPE(0,"FILE_IO")
PLOG_FRAME = PerformanceLog.PLOG_TYPE(1,"FRAME")
PLOG_CPU = PerformanceLog.PLOG_TYPE(2,"CPU")
PLOG_GPU = PerformanceLog.PLOG_TYPE(3,"GPU")

shaders = {}

class SharedVbo(object):
    def __init__(self,size=1024*1024,**kwds):
        super(SharedVbo,self).__init__(**kwds)
        self.data = np.zeros(shape=(size,),dtype=np.float32)
        self.vbo = vbo.VBO(self.data)
        self.bound = False
        self.size = size
        self.reset()
    def reset(self):
        self.avail = self.size
        self.allocated = 0
    def free(self):
        self.vbo.delete()
    def bind(self):
        PLOG(PLOG_CPU,"SharedVbo bind")
        self.vbo.bind()
        PLOG(PLOG_CPU,"SharedVbo bound")
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
        PLOG(PLOG_CPU,"SharedVbo upload")
        self.vbo.copy_data()
        PLOG(PLOG_CPU,"SharedVbo upload done")

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
        self.hasPointerFocus = False
        self.matrixDirty = False
    def render(self,scene,matrix,opacity):
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
        self.clearhover = None
        self.hidden = False
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
            d.render(self,self.matrix,1.0)
        self.renderComplete()
    def prepareToRender(self):
        pass
    def renderComplete(self):
        pass
    def input2d(self,x,y,buttons):
        if self.clearhover: self.clearhover()
        if self.eventHandler == None:
            if self.ignoreMotion:
                ignore = True
                for b in buttons:
                    if b==GLCompute.GLCompute.BUTTON_DOWN:
                        ignore = False
                # Can no longer ignore here because of tooltips.
                #if ignore:
                #    return None
            #if buttons[0]==0 and buttons[1]==0: return None
            for d in self.drawables:
                if d.ignoreInput: continue
                if d.opacity == 0.0: continue
                self.eventHandler = d.input2d(self.inputMatrix,x,y,buttons)
                if self.eventHandler != None: break
            if self.eventHandler:
                self.eventHandler.hasPointerFocus = True
            return self.eventHandler
        else:
            if self.eventHandler.motionWhileClicked or (buttons[0]==0 and buttons[1]==0):
                newEventHandler = self.eventHandler.input2d(self.inputMatrix,x,y,buttons)
                if newEventHandler != None:
                    newEventHandler.hasPointerFocus = True
                if self.eventHandler != newEventHandler:
                    self.eventHandler.hasPointerFocus = False
                self.eventHandler = newEventHandler

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
        self.matrixDirty = True
        self.clip = False
    def updateMatrix(self):
        if self.matrixDirty:
            PLOG(PLOG_CPU,"Updating matrix %d,%d"%self.pos)
            # Update matrix
            self.matrix.identity()
            self.matrix.translate(self.pos[0],self.pos[1])
            if self.rotation != 0.0:
                self.matrix.rotation(2.0*3.1415927*self.rotation/360.0)
            self.matrix.translate(-self.transformOffset[0],-self.transformOffset[1])
            if self.scale != 1.0:
                self.matrix.scale(self.scale)
            self.matrixDirty = False
            PLOG(PLOG_CPU,"Update of matrix done %d,%d"%self.pos)

    def reserve(self,space):
        self.svbobase = self.svbo.allocate(space)
        #print "reserved",self.svbobase,space
        if self.svbobase != None:
            self.svbospace = space
    def setTransformOffset(self,x,y):
        if self.transformOffset != (x,y):
            self.transformOffset = (x,y)
            self.matrixDirty = True
    def setPos(self,x,y):
        if self.pos != (x,y):
            self.pos = (x,y)
            self.matrixDirty = True
    def setScale(self,scale):
        if self.scale != scale:
            self.scale = scale
            self.matrixDirty = True
    def setRotation(self,rotation):
        if self.rotation != rotation:
            self.rotation = rotation
            self.matrixDirty = True
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
        if "maxchars" in kwargs:
            chars = kwargs["maxchars"]
            del kwargs["maxchars"]
        else:
            chars = len(args[0])+10
        if self.svbobase == None:
            #print "chars in",args[0],chars
            self.reserve(6*12*4*chars)
        texture,vertices,width,height = self.shader.label(*args,**kwargs)
        self.size = (width*self.scale,height*self.scale)
        #print vertices
        self.setVab(vertices)
        self.texture = texture
    def render(self,scene,matrix,opacity):
        PLOG(PLOG_CPU,"Geometry render %d,%d"%self.pos)
        self.updateMatrix()
        m = self.matrix.copy()
        m.mult(matrix);
        finalopacity = self.opacity * opacity
        if self.vab != None and finalopacity>0.0:
            PLOG(PLOG_CPU,"Geometry render draw %d,%d"%self.pos)
            if self.clip:
                glEnable(GL_STENCIL_TEST)
                glStencilFunc(GL_ALWAYS, 1, 0xFF);
                glStencilOp(GL_KEEP, GL_KEEP, GL_REPLACE);
                glStencilMask(0xFF);
            self.shader.draw(self.vab,self.texture,m,self.colour,finalopacity,self.edges)
            PLOG(PLOG_CPU,"Geometry render children %d,%d"%self.pos)
        if self.clip:
            glStencilFunc(GL_EQUAL, 1, 0xFF)
            glStencilMask(0x00);
        for c in self.children:
            c.render(scene,m,finalopacity) # Relative to parent
        if self.clip:
            glDisable(GL_STENCIL_TEST)
            glStencilMask(0xFF);
        PLOG(PLOG_CPU,"Geometry render done %d,%d"%self.pos)
    def input2d(self,matrix,x,y,buttons):
        # Update matrix
        self.updateMatrix()
        m = self.matrix.copy()
        m.mult(matrix);
        # Transform the scene coords into object space
        lx,ly,lz = m.multveci(x,y)
        #print lx,ly,self.size[0],self.size[1]
        handler = None
        # Try all children first
        if not self.hasPointerFocus:
            for c in self.children:
                handler = c.input2d(m,x,y,buttons)
                if handler != None:
                    break
        if (handler == None) and not self.ignoreInput and ((lx>=0.0 and lx<=(self.size[0]) and ly>=0.0 and ly<=(self.size[1])) or self.hasPointerFocus):
            handler = self.event2d(lx,ly,buttons)
        return handler # Not handled
    def event2d(self,lx,ly,buttons):
        """
        A 2d event ocurred in our active region
        """
        return None

class Button(Geometry):
    def __init__(self,width,height,onclick,onhover=None,onhoverobj=None,**kwds):
        super(Button,self).__init__(**kwds)
        self.size = (width,height)
        self.ignoreInput = False
        self.onclick = onclick
        self.notClicked = True
        self.onhover = onhover
        self.onhoverobj = onhoverobj
    def event2d(self,lx,ly,buttons):
        if buttons[0] == 1:
            # Clicked
            if self.notClicked:
                self.onclick(lx,ly)
                self.notClicked = False
            return self
        else:
            if self.onhover:
                self.onhover(self,self.onhoverobj)
            self.notClicked = True
        return None

class XYGraph(Button):
    def __init__(self,width,height,onclick,**kwds):
        super(XYGraph,self).__init__(width,height,onclick,**kwds)
        self.motionWhileClicked = True
        self.inMotion = False
    def event2d(self,lx,ly,buttons):
        if buttons[0] == 1:
            # Clicked
            self.onclick(lx,ly,self.inMotion)
            if not self.inMotion:
                self.inMotion = True
            return self
        else:
            if self.inMotion:
                self.inMotion = False
                self.onclick(lx,ly,self.inMotion)
            return None

class Text(Button):
    def __init__(self,text="",**kwds):
        self.text = text
        self.oldtext = None
        self.maxchars = 64*20
        super(Text,self).__init__(0,0,onclick=self.clickHandler,**kwds)
        #self.motionWhileClicked = True
    def update(self):
        if self.oldtext != self.text:
            text = self.text
            if len(text)>self.maxchars:
                text = text[:self.maxchars]
            self.label(text,maxchars=self.maxchars)
            self.oldtext = self.text
    def clickHandler(self,x,y):
        pass
    def event2d(self,lx,ly,buttons):
        if buttons[0] == 1:
            # Clicked
            self.onclick(lx,ly)
            return self
        return None
    def key(self,k,m):
        if k==GLCompute.GLCompute.KEY_BACKSPACE:
            self.text = self.text[:-1]
        elif k>=GLCompute.GLCompute.KEY_A and k<=GLCompute.GLCompute.KEY_Z:
            c = k - GLCompute.GLCompute.KEY_A
            if m&GLCompute.GLCompute.KEY_MOD_SHIFT:
                c = c + ord('A')
            else:
                c = c + ord('a')
            self.text += chr(c)
        else:
            print "edit",k

class Flickable(Button):
    def __init__(self,width,height,**kwds):
        super(Flickable,self).__init__(width,height,self.clickdrag,**kwds)
        self.motionWhileClicked = True
        self.offsetx = 0
        self.offsety = 0
        self.dragging = False
        self.dragstartx = 0
        self.dragstarty = 0
        self.canvdragstartx = 0
        self.canvdragstarty = 0
        self.allowx = True
        self.allowy = True
    def event2d(self,lx,ly,buttons):
        if buttons[0] == 1:
            if self.dragging == False:
                self.dragging = True
                self.dragstartx = lx
                self.dragstarty = ly
                if len(self.children)>0:
                    self.canvdragstartx,self.canvdragstarty = self.children[0].pos
            # Clicked
            self.onclick(lx,ly)
            return self
        else:
            self.dragging = False
            return None
    def clickdrag(self,x,y):
        if len(self.children)>0:
            w,h = self.size
            cw,ch = self.children[0].size
            miny = min(0,h - ch)
            maxy = max(0,h - ch)
            minx = min(0,w - cw)
            maxx = max(0,w - cw)
            newx,newy = self.children[0].pos
            #print w,h,cw,ch,miny,maxy,newy
            if self.allowx:
                newx = self.canvdragstartx + (x-self.dragstartx)
            if self.allowy:
                newy = self.canvdragstarty + (y-self.dragstarty)
            newy = max(newy,miny)
            newy = min(newy,maxy)
            newx = max(newx,minx)
            newx = min(newx,maxx)
            #print newx,newy
            self.children[0].setPos(newx,newy)

