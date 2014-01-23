"""
GLComputeGLFW.py
(c) Andrew Baldwin 2013-2014

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

"""

# standard python imports. Should not be missing
import sys,time

# OpenGL. Could be missing
try:
    from OpenGL.GL import *
    #from OpenGL.arrays import vbo
    #from OpenGL.GL.shaders import compileShader, compileProgram
    from OpenGL.GL.framebufferobjects import *
    #from OpenGL.GL.ARB.texture_rg import *
    #from OpenGL.GL.EXT.framebuffer_object import *
except Exception,err:
    print """There is a problem with your python environment.
I Could not import the pyOpenGL module.
On Debian/Ubuntu try "sudo apt-get install python-opengl"
"""
    sys.exit(1)

# pyGLFW
import glfw

from datetime import datetime
def timeInUsec():
    dt = datetime.now()
    return dt.day*3600.0*24.0+dt.hour*3600.0+dt.minute*60.0+dt.second+0.000001*dt.microsecond

class GLCompute(object):
    KEY_ESCAPE = glfw.GLFW_KEY_ESCAPE
    KEY_TAB = glfw.GLFW_KEY_TAB
    KEY_SPACE = glfw.GLFW_KEY_SPACE
    KEY_PERIOD = glfw.GLFW_KEY_PERIOD
    KEY_COMMA = glfw.GLFW_KEY_COMMA
    KEY_ZERO = glfw.GLFW_KEY_0
    KEY_ONE = glfw.GLFW_KEY_1
    KEY_TWO = glfw.GLFW_KEY_2
    KEY_THREE = glfw.GLFW_KEY_3
    KEY_FOUR = glfw.GLFW_KEY_4
    KEY_FIVE = glfw.GLFW_KEY_5
    KEY_SIX = glfw.GLFW_KEY_6
    KEY_SEVEN = glfw.GLFW_KEY_7
    KEY_EIGHT = glfw.GLFW_KEY_8
    KEY_NINE = glfw.GLFW_KEY_9

    KEY_A = glfw.GLFW_KEY_A
    KEY_B = glfw.GLFW_KEY_B
    KEY_D = glfw.GLFW_KEY_D
    KEY_E = glfw.GLFW_KEY_E
    KEY_N = glfw.GLFW_KEY_N
    KEY_M = glfw.GLFW_KEY_M
    KEY_Q = glfw.GLFW_KEY_Q
    KEY_T = glfw.GLFW_KEY_T
    KEY_V = glfw.GLFW_KEY_V

    KEY_LEFT = glfw.GLFW_KEY_LEFT
    KEY_RIGHT = glfw.GLFW_KEY_RIGHT
    KEY_UP = glfw.GLFW_KEY_UP
    KEY_DOWN = glfw.GLFW_KEY_DOWN

    def __init__(self,width=640,height=360,**kwds):
        if not glfw.glfwInit():
            print "Could not init GLFW"
            sys.exit(1)
        self.width = width  
        self.height = height
        self.glfwMonitor = glfw.glfwGetPrimaryMonitor()
        self.glfwWindow = glfw.glfwCreateWindow(width,height,self.windowName(),None,None)
        self.installCallbacks(self.glfwWindow)
        glfw.glfwMakeContextCurrent(self.glfwWindow)
        self._isFull = False
        self._start = time.time()
        self._frames = 0
        self._fps = 25
        self._last = time.time()
        self._drawNeeded = True
        self.scenes = [] # Render these scenes in order
        super(GLCompute,self).__init__(**kwds)
    def installCallbacks(self,w):
        glfw.glfwSetWindowRefreshCallback(w,self.redisplay)
        glfw.glfwSetKeyCallback(w, self.__key)
    def toggleFullscreen(self):
        if not self._isFull:
            monitors = glfw.glfwGetMonitors()
            m = monitors[0]
            mode = glfw.glfwGetVideoMode(m)
            self.glfwFullscreenWindow = glfw.glfwCreateWindow(mode[0],mode[1],self.windowName(),m,self.glfwWindow)
            self.installCallbacks(self.glfwFullscreenWindow)
            glfw.glfwHideWindow(self.glfwWindow)
            self._isFull = True
            self.redisplay()
        else:
            glfw.glfwDestroyWindow(self.glfwFullscreenWindow)
            glfw.glfwShowWindow(self.glfwWindow)
            self._isFull = False
            self.redisplay()
    def run(self):
        while not glfw.glfwWindowShouldClose(self.glfwWindow):
            if self._drawNeeded:
                if self._isFull:
                    glfw.glfwMakeContextCurrent(self.glfwFullscreenWindow)
                else:
                    glfw.glfwMakeContextCurrent(self.glfwWindow)
                self.__draw()
                if self._isFull:
                    glfw.glfwSwapBuffers(self.glfwFullscreenWindow)
                else:
                    glfw.glfwSwapBuffers(self.glfwWindow)
                self._drawNeeded = False
            glfw.glfwPollEvents()
            self.onIdle()
        glfw.glfwTerminate()
    def windowName(self):
        return "GLCompute"
    def renderScenes(self):
        for s in self.scenes:
            s.render(self._frames)
    def __draw(self):
        self._last = timeInUsec()
        self.onFboDraw()
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        if self._isFull:
            w,h = glfw.glfwGetWindowSize(self.glfwFullscreenWindow)
        else: 
            w,h = glfw.glfwGetWindowSize(self.glfwWindow)
        self.width = w
        self.height = h
        glViewport(0,0,w,h)
        glClearColor(0.0,0.0,0.0,1)
        glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
        try:
            self.onDraw(w,h)
        except:
            import traceback
            traceback.print_exc()
            return    
        self._frames+=1
    def onFboDraw(self):
        pass
    def onDraw(self,width,height):
        pass
    def __idle(self):
        self.onIdle()
    def redisplay(self,window=None):
        self._drawNeeded = True
    def onIdle(self):
        pass
    def __key(self,window, key, scancode, action, mods):
        # Don't propagate release events
        if action == glfw.GLFW_PRESS or action == glfw.GLFW_REPEAT:
            self.key(key)
    def exit(self):
        pass
    def key(self,k):
        if k == self.KEY_ESCAPE:
            glfw.glfwSetWindowShouldClose(self.glfwWindow,1)
            self.exit()
        if k == self.KEY_TAB:
            self.toggleFullscreen()
