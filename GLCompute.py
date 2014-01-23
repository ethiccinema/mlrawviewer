"""
GLCompute.py
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

This is a simple framework for doing (graphics) 
computation and display using OpenGL FBOs

"""

# standard python imports. Should not be missing
import sys,time,os,os.path

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

def glarray(gltype, seq):
    carray = (gltype * len(seq))()
    carray[:] = seq
    return carray

class Shader(object):
    def __init__(self,vs,fs,uniforms,**kwds):
        vertexShaderHandle = compileShader(vs,GL_VERTEX_SHADER)
        fragmentShaderHandle = compileShader(fs,GL_FRAGMENT_SHADER)
        self.program = compileProgram(vertexShaderHandle,fragmentShaderHandle)
        self.vertex = glGetAttribLocation(self.program, "vertex")
        self.uniforms = {}
        for key in uniforms:
            self.uniforms[key] = glGetUniformLocation(self.program,key)
        super(Shader,self).__init__(**kwds)
    def use(self):
        glUseProgram(self.program)

class Texture:
    def __init__(self,size,rgbadata=None,hasalpha=True,mono=False,sixteen=False,mipmap=False,fp=False):
        self.mono = mono
        self.hasalpha = hasalpha
        self.sixteen = sixteen
        self.fp = fp
        self.id = glGenTextures(1)
        self.width = size[0]
        self.height = size[1]
        self.fbo = None
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D,self.id)
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
        if hasalpha and not fp:
            glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA,self.width,self.height,0,GL_RGBA,GL_UNSIGNED_BYTE,rgbadata)
        elif hasalpha and fp:
            glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA32F,self.width,self.height,0,GL_RGBA,GL_FLOAT,None)
        elif not hasalpha and not mono and fp:
            glTexImage2D(GL_TEXTURE_2D,0,GL_RGB32F,self.width,self.height,0,GL_RGB,GL_FLOAT,None)
        elif mono and not sixteen:
            try: glTexImage2D(GL_TEXTURE_2D,0,GL_RED,self.width,self.height,0,GL_RED,GL_UNSIGNED_BYTE,rgbadata)
            except GLError: glTexImage2D(GL_TEXTURE_2D,0,GL_RGB,self.width,self.height,0,GL_RED,GL_UNSIGNED_BYTE,rgbadata)
        elif mono and sixteen:
            try: glTexImage2D(GL_TEXTURE_2D,0,GL_R16,self.width,self.height,0,GL_RED,GL_UNSIGNED_SHORT,rgbadata)
            except GLError: glTexImage2D(GL_TEXTURE_2D,0,GL_RGB16,self.width,self.height,0,GL_RED,GL_UNSIGNED_SHORT,rgbadata)
        elif not mono and sixteen:
            try: glTexImage2D(GL_TEXTURE_2D,0,GL_RGB32F,self.width,self.height,0,GL_RGB,GL_UNSIGNED_SHORT,rgbadata)
            except GLError: glTexImage2D(GL_TEXTURE_2D,0,GL_RGB16,self.width,self.height,0,GL_RGB,GL_UNSIGNED_SHORT,rgbadata)
        else:
            glTexImage2D(GL_TEXTURE_2D,0,GL_RGB,self.width,self.height,0,GL_RGB,GL_UNSIGNED_BYTE,rgbadata)
        if mipmap:
            glGenerateMipmap(GL_TEXTURE_2D)
        self.mipmap = mipmap
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glBindTexture(GL_TEXTURE_2D,0)
        self.setupFbo()
        glBindFramebuffer(GL_FRAMEBUFFER, 0)

    def setupFbo(self):
        self.fbo = glGenFramebuffers(1)
        glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)
        try:
            glFramebufferTexture2DEXT(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D,self.id, 0)
        except:
	    pass

    def addmipmap(self):
        self.mipmap = True
        self.bindtex()
        glGenerateMipmap(GL_TEXTURE_2D)

    def update(self,rgbadata=None):
        self.bindtex()
        if self.hasalpha and not self.fp:
            glTexSubImage2D(GL_TEXTURE_2D,0,0,0,self.width,self.height,GL_RGBA,GL_UNSIGNED_BYTE,rgbadata)
        elif self.hasalpha and self.fp:
            glTexSubImage2D(GL_TEXTURE_2D,0,0,0,self.width,self.height,GL_RGBA,GL_FLOAT,rgbadata)
        elif not self.hasalpha and not self.mono and self.fp:
            glTexSubImage2D(GL_TEXTURE_2D,0,0,0,self.width,self.height,GL_RGB,GL_FLOAT,rgbadata)
        elif self.mono and not self.sixteen:
            glTexSubImage2D(GL_TEXTURE_2D,0,0,0,self.width,self.height,GL_RED,GL_UNSIGNED_BYTE,rgbadata)
        elif self.sixteen and self.mono:
            glTexSubImage2D(GL_TEXTURE_2D,0,0,0,self.width,self.height,GL_RED,GL_UNSIGNED_SHORT,rgbadata)
        elif self.sixteen and not self.mono:
            glTexSubImage2D(GL_TEXTURE_2D,0,0,0,self.width,self.height,GL_RGB,GL_UNSIGNED_SHORT,rgbadata)
        else:
            glTexSubImage2D(GL_TEXTURE_2D,0,0,0,self.width,self.height,GL_RGB,GL_UNSIGNED_BYTE,rgbadata)
        if self.mipmap:
            glGenerateMipmap(GL_TEXTURE_2D)

    def bindfbo(self):
        try:
            glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)
            err = glGetError()
            if err!=0:
                raise Exception()
        except:
            self.setupFbo()
            glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)
        glViewport(0,0,self.width,self.height)

    def bindtex(self,linear=False,texnum=0):
        glActiveTexture(GL_TEXTURE0+texnum)
        glBindTexture(GL_TEXTURE_2D, self.id)
        if linear:
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            if not self.mipmap:
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            else:
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR)
        else:
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
            if not self.mipmap:

                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
            else:
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST_MIPMAP_NEAREST)


from datetime import datetime
def timeInUsec():
    dt = datetime.now()
    return dt.day*3600.0*24.0+dt.hour*3600.0+dt.minute*60.0+dt.second+0.000001*dt.microsecond

class Drawable(object):
    def __init__(self):
        pass
    def render(self,scene):
        pass

class Scene(object):
    def __init__(self,size):
        self.drawables = []
        self.size = size
        self.position = (0, 0)
    def setTarget(self):
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        glViewport(self.position[0],self.position[1],self.size[0],self.size[1])
    def render(self,frame):
        self.frame = frame
        self.prepareToRender()
        self.setTarget()
        for d in self.drawables:
            d.render(self)
        self.renderComplete()
    def prepareToRender(self):
        pass
    def renderComplete(self):
        pass

def glfwp(name):
    return os.path.join(os.path.split(__file__)[0],name)

try:
    candidates = ["libglfw.so.3","glfw3.dll","libglfw3.dylib"]
    for c in candidates:
        if os.path.exists(glfwp(c)):
	     os.environ['GLFW_LIBRARY'] = glfwp(c)
	     break
    from GLComputeGLFW import GLCompute
    print "Using GLFW"
    # Prefer the GFLW version
except:
    from GLComputeGLUT import GLCompute
    print "Using GLUT instead of GLFW. Some features may be disabled."
    # Fallback, potentially more limited
