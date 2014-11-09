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
    from OpenGL.GL.shaders import compileShader,ShaderProgram
    from OpenGL.GL.framebufferobjects import *
    from OpenGL.GL.ARB.texture_rg import *
    from OpenGL.GL.ARB.texture_float import *
    from OpenGL.GL.EXT.framebuffer_object import *
except Exception,err:
    print """There is a problem with your python environment.
I Could not import the pyOpenGL module.
On Debian/Ubuntu try "sudo apt-get install python-opengl"
"""
    sys.exit(1)

import PerformanceLog
from PerformanceLog import PLOG
PLOG_FILE_IO = PerformanceLog.PLOG_TYPE(0,"FILE_IO")
PLOG_FRAME = PerformanceLog.PLOG_TYPE(1,"FRAME")
PLOG_CPU = PerformanceLog.PLOG_TYPE(2,"CPU")
PLOG_GPU = PerformanceLog.PLOG_TYPE(3,"GPU")


def glarray(gltype, seq):
    carray = (gltype * len(seq))()
    carray[:] = seq
    return carray

def mrvCompileProgramPreValidate(*shaders, **named):
    program = glCreateProgram()
    for shader in shaders:
        glAttachShader(program, shader)
    program = ShaderProgram( program )
    glLinkProgram(program)
    return program

def mrvCompileProgramPostValidate(program, *shaders, **named):
    if hasattr(program,"check_validate"):
        program.check_validate()
    if hasattr(program,"check_linked"):
        program.check_linked()
    for shader in shaders:
        glDeleteShader(shader)
    return program

class ContextState(object):
    def __init__(self):
        self.current_shader = None
        self.blending = False
        self.current_texture = (None,False)
    def reset_state(self):
        self.current_shader = None
        self.blending = False
        self.current_texture = (None,False)

SharedContextState = ContextState()

class Shader(object):
    def __init__(self,vs,fs,uniforms,**kwds):
        vertexShaderHandle = compileShader(vs,GL_VERTEX_SHADER)
        fragmentShaderHandle = compileShader(fs,GL_FRAGMENT_SHADER)
        self.program = mrvCompileProgramPreValidate(vertexShaderHandle,fragmentShaderHandle)
        try:
            self.vertex = glGetAttribLocation(self.program, "vertex")
        except:
            self.program = None
        if not self.program: return
        self.uniforms = {}
        for key in uniforms:
            self.uniforms[key] = glGetUniformLocation(self.program,key)
        self.context = SharedContextState
        self.preValidateConfig()
        mrvCompileProgramPostValidate(self.program,vertexShaderHandle,fragmentShaderHandle)
        super(Shader,self).__init__(**kwds)
    def preValidateConfig(self):
        pass
    def use(self):
        if self.context.current_shader != self:
            PLOG(PLOG_CPU,"Changing shader")
            glUseProgram(self.program)
            self.context.current_shader = self
    def blend(self,state):
        if state and not self.context.blending:
            glBlendFunc(GL_ONE, GL_ONE_MINUS_SRC_ALPHA)
            glEnable(GL_BLEND)
            self.context.blending = state
        elif not state and self.context.blending:
            glDisable(GL_BLEND)
            self.context.blending = state

class Texture1D:
    """ 1D texture, for 1D LUTs. Floats only """
    def __init__(self,size,data):
        self.context = SharedContextState
        glEnable(GL_TEXTURE_1D)
        self.id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_1D,self.id)
        glTexParameteri(GL_TEXTURE_1D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_1D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_1D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexImage1D(GL_TEXTURE_1D, 0, GL_RGB32F, size, 0, GL_RGB, GL_FLOAT, data)
        self.size = size
    def bindtex(self,texnum=0,linear=False):
        if self.context.current_texture == (self,True):
            return
        glActiveTexture(GL_TEXTURE0+texnum)
        glBindTexture(GL_TEXTURE_1D, self.id)
        if not linear:
            glTexParameteri(GL_TEXTURE_1D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
            glTexParameteri(GL_TEXTURE_1D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        else:
            glTexParameteri(GL_TEXTURE_1D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_1D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        self.context.current_texture = (self,True)
    def free(self):
        glDeleteTextures(self.id)

class Texture3D:
    """ 3D texture, for 3D LUTs. Floats only """
    def __init__(self,size,data):
        self.context = SharedContextState
        glEnable(GL_TEXTURE_3D)
        self.id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_3D,self.id)
        glTexParameteri(GL_TEXTURE_3D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_3D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_3D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_3D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_3D, GL_TEXTURE_WRAP_R, GL_CLAMP_TO_EDGE)
        glTexImage3D(GL_TEXTURE_3D, 0, GL_RGB32F, size, size, size, 0, GL_RGB, GL_FLOAT, data)
        self.size = size
    def bindtex(self,texnum=0,linear=False):
        if self.context.current_texture == (self,True):
            return
        glActiveTexture(GL_TEXTURE0+texnum)
        glBindTexture(GL_TEXTURE_3D, self.id)
        if not linear:
            glTexParameteri(GL_TEXTURE_3D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
            glTexParameteri(GL_TEXTURE_3D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        else:
            glTexParameteri(GL_TEXTURE_3D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_3D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        self.context.current_texture = (self,True)
    def free(self):
        glDeleteTextures(self.id)


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
        self.atlas = []
        self.atlasuh = 0 # Atlas is full down to this row
        self.atlasfh = 0 # Atlas is being filled down to here
        self.atlasfw = 0 # Atlas is being filled along to here
        self.context = SharedContextState
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D,self.id)
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
        #print "Max texture size",glGetInteger(GL_MAX_TEXTURE_SIZE)
        #print "Max 3D texture size",glGetInteger(GL_MAX_3D_TEXTURE_SIZE)
        if hasalpha and not fp and not sixteen:
            glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA,self.width,self.height,0,GL_RGBA,GL_UNSIGNED_BYTE,rgbadata)
        elif hasalpha and fp:
            glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA32F,self.width,self.height,0,GL_RGBA,GL_FLOAT,None)
        elif not hasalpha and mono and fp:
            try: glTexImage2D(GL_TEXTURE_2D,0,GL_LUMINANCE32F_ARB,self.width,self.height,0,GL_RED,GL_FLOAT,None)
            except GLError: glTexImage2D(GL_TEXTURE_2D,0,GL_RGB32F,self.width,self.height,0,GL_RED,GL_FLOAT,None)
        elif not hasalpha and not mono and fp:
            glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA32F,self.width,self.height,0,GL_RGB,GL_FLOAT,None)
        elif mono and not sixteen:
            try: glTexImage2D(GL_TEXTURE_2D,0,GL_RED,self.width,self.height,0,GL_RED,GL_UNSIGNED_BYTE,rgbadata)
            except GLError: glTexImage2D(GL_TEXTURE_2D,0,GL_RGB,self.width,self.height,0,GL_RED,GL_UNSIGNED_BYTE,rgbadata)
        elif mono and sixteen:
            try: glTexImage2D(GL_TEXTURE_2D,0,GL_R16,self.width,self.height,0,GL_RED,GL_UNSIGNED_SHORT,rgbadata)
            except GLError: glTexImage2D(GL_TEXTURE_2D,0,GL_RGB16,self.width,self.height,0,GL_RED,GL_UNSIGNED_SHORT,rgbadata)
        elif not mono and sixteen and hasalpha:
            try:
                glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA32F,self.width,self.height,0,GL_RGBA,GL_UNSIGNED_SHORT,rgbadata)
            except GLError:
                glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA16,self.width,self.height,0,GL_RGBA,GL_UNSIGNED_SHORT,rgbadata)
        elif not mono and sixteen and not hasalpha:
            try:
                glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA32F,self.width,self.height,0,GL_RGB,GL_UNSIGNED_SHORT,rgbadata)
            except GLError:
                glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA16,self.width,self.height,0,GL_RGB,GL_UNSIGNED_SHORT,rgbadata)
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

    def free(self):
        import OpenGL.GL.framebufferobjects
        if bool(OpenGL.GL.framebufferobjects.glDeleteFramebuffers):
            OpenGL.GL.framebufferobjects.glDeleteFramebuffers((self.fbo,))
        elif bool(OpenGL.GL.framebufferobjects.glDeleteFramebuffersEXT):
            OpenGL.GL.framebufferobjects.glDeleteFramebuffersEXT((self.fbo,))
        else:
            print "Could not delete framebuffer",self.fbo
        glDeleteTextures(self.id)

    def setupFbo(self):
        self.fbo = glGenFramebuffers(1)
        glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)
        try:
            glFramebufferTexture2DEXT(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D,self.id, 0)
        except:
            pass
	ok = glCheckFramebufferStatus(GL_FRAMEBUFFER)
	if ok != GL_FRAMEBUFFER_COMPLETE:
		print "Framebuffer not complete!:",ok,self.mono,self.hasalpha,self.fp,self.sixteen

    def addmipmap(self):
        self.mipmap = True
        self.bindtex()
        glGenerateMipmap(GL_TEXTURE_2D)

    def atlasadd(self,rgbadata,width,height):
        """
        Add given image as subimage within this texture
        Remember the coordinates for use later
        Return None if there wasn't space in this texture
        else returns index of this atlas item
        Atlas filling is not very optimised, just filling a current row until it needs to start the next one
        Will work best with identical sized frames and a texture optimised for a multiple of those
        """
        if (self.atlasuh + height) > self.height:
            return None # Too high for current row
        if width > self.width:
            return None # Too wide for current texture
        yoff = self.atlasuh
        xoff = self.atlasfw
        newuh = self.atlasuh
        newfw = self.atlasfw + width
        newfh = self.atlasfh
        if (self.atlasuh + height) > newfh:
            newfh = self.atlasuh + height # Expand the current row height
        if newfw > self.width:
            if (self.atlasfh + height) > self.height:
                return None # Too high for new row
            newfw = width
            xoff = 0
            yoff = self.atlasfh
            newuh = self.atlasfh
            newfh = newuh + height
        # Update the texture
        self.update(rgbadata,xoff,yoff,width,height)
        # Only gets here if texture update did not raise exception
        # Remember coordinates for texture and add to atlas. (x,y,w,h) in texture space
        uvx = float(xoff)/float(self.width)
        uvy = float(yoff)/float(self.height)
        uvw = float(width)/float(self.width)
        uvh = float(height)/float(self.height)
        self.atlas.append((uvx,uvy,uvw,uvh))
        self.atlasuh = newuh
        self.atlasfh = newfh
        self.atlasfw = newfw
        return len(self.atlas)-1

    def atlasempty(self):
        self.atlas = []
        self.atlasuh = 0 # Atlas is full down to this row
        self.atlasfh = 0 # Atlas is being filled down to here
        self.atlasfw = 0 # Atlas is being filled along to here

    def update(self,rgbadata=None,xoff=0,yoff=0,width=None,height=None):
        w = width
        if (w==None):
            w = self.width
        h = height
        if (h==None):
            h = self.height

        self.bindtex()
        if self.hasalpha and not self.fp:
            glTexSubImage2D(GL_TEXTURE_2D,0,xoff,yoff,w,h,GL_RGBA,GL_UNSIGNED_BYTE,rgbadata)
        elif self.hasalpha and self.fp:
            glTexSubImage2D(GL_TEXTURE_2D,0,xoff,yoff,w,h,GL_RGBA,GL_FLOAT,rgbadata)
        elif not self.hasalpha and not self.mono and self.fp:
            glTexSubImage2D(GL_TEXTURE_2D,0,xoff,yoff,w,h,GL_RGB,GL_FLOAT,rgbadata)
        elif not self.hasalpha and self.mono and self.fp:
            glTexSubImage2D(GL_TEXTURE_2D,0,xoff,yoff,w,h,GL_RED,GL_FLOAT,rgbadata)
        elif self.mono and not self.sixteen:
            glTexSubImage2D(GL_TEXTURE_2D,0,xoff,yoff,w,h,GL_RED,GL_UNSIGNED_BYTE,rgbadata)
        elif self.sixteen and self.mono:
            glTexSubImage2D(GL_TEXTURE_2D,0,xoff,yoff,w,h,GL_RED,GL_UNSIGNED_SHORT,rgbadata)
        elif self.sixteen and not self.mono and not self.hasalpha:
            glTexSubImage2D(GL_TEXTURE_2D,0,xoff,yoff,w,h,GL_RGB,GL_UNSIGNED_SHORT,rgbadata)
        elif self.sixteen and not self.mono and self.hasalpha:
            glTexSubImage2D(GL_TEXTURE_2D,0,xoff,yoff,w,h,GL_RGBA,GL_UNSIGNED_SHORT,rgbadata)
        else:
            glTexSubImage2D(GL_TEXTURE_2D,0,xoff,yoff,w,h,GL_RGB,GL_UNSIGNED_BYTE,rgbadata)
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

    @staticmethod
    def unbindtex(texnum=0,context=SharedContextState):
        if texnum==0:
            context.current_texture = (None,False)
        glActiveTexture(GL_TEXTURE0+texnum)
        glBindTexture(GL_TEXTURE_2D, 0)

    def bindtex(self,linear=False,texnum=0):
        if self.context.current_texture == (self,linear):
            return
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
        self.context.current_texture = (self,linear)

from datetime import datetime
def timeInUsec():
    dt = datetime.now()
    return dt.day*3600.0*24.0+dt.hour*3600.0+dt.minute*60.0+dt.second+0.000001*dt.microsecond

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
    import traceback
    traceback.print_exc()
