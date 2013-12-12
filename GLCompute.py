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
import sys,urllib,urllib2,json,time

# OpenGL. Could be missing
try:
    from OpenGL.GL import *
    from OpenGL.GLUT import *
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
    def __init__(self,size,rgbadata=None,hasalpha=True,mono=False,sixteen=False):
        self.mono = mono
        self.hasalpha = hasalpha
        self.sixteen = sixteen
        self.id = glGenTextures(1)
        self.width = size[0]
        self.height = size[1]
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D,self.id)
        if hasalpha:
            glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA,self.width,self.height,0,GL_RGBA,GL_UNSIGNED_BYTE,rgbadata)
        elif mono and sixteen:
            glTexImage2D(GL_TEXTURE_2D,0,GL_R32F,self.width,self.height,0,GL_RED,GL_UNSIGNED_SHORT,rgbadata)
        elif not mono and sixteen:
            glTexImage2D(GL_TEXTURE_2D,0,GL_RGB32F,self.width,self.height,0,GL_RGB,GL_UNSIGNED_SHORT,rgbadata)
        else:
            glTexImage2D(GL_TEXTURE_2D,0,GL_RGB,self.width,self.height,0,GL_RGB,GL_UNSIGNED_BYTE,rgbadata)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glBindTexture(GL_TEXTURE_2D,0)
        self.fbo = glGenFramebuffers(1)
        glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)
        glFramebufferTexture2DEXT(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D,self.id, 0)
        glBindFramebuffer(GL_FRAMEBUFFER, 0)

    def update(self,rgbadata=None):
        self.bindtex()
        if self.hasalpha:
            glTexSubImage2D(GL_TEXTURE_2D,0,0,0,self.width,self.height,GL_RGBA,GL_UNSIGNED_BYTE,rgbadata)
        elif self.sixteen and self.mono:
            glTexSubImage2D(GL_TEXTURE_2D,0,0,0,self.width,self.height,GL_RED,GL_UNSIGNED_SHORT,rgbadata)
        elif self.sixteen and not self.mono:
            glTexSubImage2D(GL_TEXTURE_2D,0,0,0,self.width,self.height,GL_RGB,GL_UNSIGNED_SHORT,rgbadata)
        else:
            glTexSubImage2D(GL_TEXTURE_2D,0,0,0,self.width,self.height,GL_RGB,GL_UNSIGNED_BYTE,rgbadata)

    def bindfbo(self):
        glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)
        glViewport(0,0,self.width,self.height)

    def bindtex(self,linear=False):
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.id)
        if linear:
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        else:
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)

from datetime import datetime
def timeInUsec():
    dt = datetime.now()
    return dt.day*3600.0*24.0+dt.hour*3600.0+dt.minute*60.0+dt.second+0.000001*dt.microsecond

class GLCompute(object):
    def __init__(self,width=640,height=360,**kwds):
        glutInit(sys.argv) 
        glutInitDisplayMode(GLUT_DOUBLE|GLUT_RGB|GLUT_DEPTH)
        glutInitWindowSize(width,height)
        glutInitWindowPosition(0,0)
        glutCreateWindow(self.windowName())
        glutSetWindowTitle(self.windowName())  
        glutDisplayFunc(self.__draw)
        glutIdleFunc(self.__idle)
        try: 
            glutCloseFunc(self.__close)
            glutSetOption(GLUT_ACTION_ON_WINDOW_CLOSE,GLUT_ACTION_GLUTMAINLOOP_RETURNS)
        except:
            pass # Hmm... doesn't work on Mac
        glutKeyboardFunc(self.__key)
        glutSpecialFunc(self.__skey)
        self._isFull = False
        self._start = time.time()
        self._frames = 0
        self._fps = 25
        self._last = time.time()
        super(GLCompute,self).__init__(**kwds)
    def run(self):
        glutMainLoop()
    def windowName(self):
        return "GLCompute"
    def __draw(self):
        self._last = timeInUsec()
        self.onFboDraw()
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        w = glutGet(GLUT_WINDOW_WIDTH)
        h = glutGet(GLUT_WINDOW_HEIGHT)
        glViewport(0,0,w,h)
        glClearColor(0.0,0.0,0.0,1)
        glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
        self.onDraw(w,h)
        glutSwapBuffers()
        self._frames+=1
    def onFboDraw(self):
        pass
    def onDraw(self,width,height):
        pass
    def __idle(self):
        self.onIdle()
        now = timeInUsec()
        if (now-self._last >= (1.0/self._fps-0.005)):
            #print now,self._last,1.0/self._fps
            glutPostRedisplay()
    def onIdle(self):
        pass
    def __close(self):
        try:
            glutLeaveMainLoop()
        except:
            sys.exit(0) # Needed on Mac
    def __key(self,k,x,y):
        if ord(k)==27:
            self.__close()
        if ord(k)==9:
            if self._isFull:
                glutReshapeWindow(640,360)
                self._isFull = False
            else:
                glutFullScreen()
                self._isFull = True
    def __skey(self,k,x,y):
        print "special",k,x,y



