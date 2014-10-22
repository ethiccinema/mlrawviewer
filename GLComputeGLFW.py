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
import sys,time,os,threading,Queue

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
    KEY_C = glfw.GLFW_KEY_C
    KEY_D = glfw.GLFW_KEY_D
    KEY_E = glfw.GLFW_KEY_E
    KEY_F = glfw.GLFW_KEY_F
    KEY_G = glfw.GLFW_KEY_G
    KEY_H = glfw.GLFW_KEY_H
    KEY_I = glfw.GLFW_KEY_I
    KEY_J = glfw.GLFW_KEY_J
    KEY_K = glfw.GLFW_KEY_K
    KEY_L = glfw.GLFW_KEY_L
    KEY_M = glfw.GLFW_KEY_M
    KEY_N = glfw.GLFW_KEY_N
    KEY_O = glfw.GLFW_KEY_O
    KEY_P = glfw.GLFW_KEY_P
    KEY_Q = glfw.GLFW_KEY_Q
    KEY_R = glfw.GLFW_KEY_R
    KEY_S = glfw.GLFW_KEY_S
    KEY_T = glfw.GLFW_KEY_T
    KEY_U = glfw.GLFW_KEY_U
    KEY_V = glfw.GLFW_KEY_V
    KEY_W = glfw.GLFW_KEY_W
    KEY_X = glfw.GLFW_KEY_X
    KEY_Y = glfw.GLFW_KEY_Y
    KEY_Z = glfw.GLFW_KEY_Z

    KEY_BACKSPACE = glfw.GLFW_KEY_BACKSPACE

    KEY_LEFT = glfw.GLFW_KEY_LEFT
    KEY_RIGHT = glfw.GLFW_KEY_RIGHT
    KEY_UP = glfw.GLFW_KEY_UP
    KEY_DOWN = glfw.GLFW_KEY_DOWN

    KEY_MOD_SHIFT = glfw.GLFW_MOD_SHIFT
    KEY_MOD_CONTROL= glfw.GLFW_MOD_CONTROL
    KEY_MOD_ALT = glfw.GLFW_MOD_ALT

    BUTTON_DOWN = 1
    BUTTON_UP = 0
    BUTTON_LEFT = 0
    BUTTON_RIGHT = 1

    def __init__(self,width=640,height=360,**kwds):
        cwd = os.getcwd()
        if not glfw.glfwInit():
            print "Could not init GLFW"
            sys.exit(1)
        os.chdir(cwd) # GLFW changes it, which causes problems
        self.width = width
        self.height = height
        self.glfwMonitor = glfw.glfwGetPrimaryMonitor()
        glfw.glfwWindowHint(glfw.GLFW_RED_BITS, 8)
        glfw.glfwWindowHint(glfw.GLFW_GREEN_BITS, 8)
        glfw.glfwWindowHint(glfw.GLFW_BLUE_BITS, 8)
        glfw.glfwWindowHint(glfw.GLFW_ALPHA_BITS, 8)
        glfw.glfwWindowHint(glfw.GLFW_STENCIL_BITS, 8)
        glfw.glfwWindowHint(glfw.GLFW_DECORATED,False)
        glfw.glfwWindowHint(glfw.GLFW_RESIZABLE,False)
        glfw.glfwWindowHint(glfw.GLFW_VISIBLE,False)
        self.backgroundWindow = glfw.glfwCreateWindow(1,1,self.bgWindowName(),None,None)
        self.bgDrawn = False
        self.bgActive = False
        self.bgVisibility = 0
        self.bgsync = None
        try:
            self.hasSync = glFenceSync
            self.hasSync = False # True # - Doesn't work on Mac/Win
        except:
            self.hasSync = False
        self.bgThread = None
        self.bgControl = Queue.Queue()
        glfw.glfwWindowHint(glfw.GLFW_DECORATED,True)
        glfw.glfwWindowHint(glfw.GLFW_RESIZABLE,True)
        glfw.glfwWindowHint(glfw.GLFW_VISIBLE,True)
        uname = self.windowName().encode("utf-8")
        self.glfwWindow = glfw.glfwCreateWindow(width,height,uname,None,None)
        glfw.glfwSwapInterval(1)
        self.installCallbacks(self.glfwWindow)
        glfw.glfwMakeContextCurrent(self.glfwWindow)
        self._isFull = False
        self._start = time.time()
        self._frames = 0
        self._fps = 25
        self._last = time.time()
        self._drawNeeded = True
        self.scenes = [] # Render these scenes in order
        self.buttons = [self.BUTTON_UP,self.BUTTON_UP]
        self.cursorVisible = None
        super(GLCompute,self).__init__(**kwds)
    def updateWindowName(self):
        uname = self.windowName().encode("utf-8")
        if not self._isFull:
            glfw.glfwSetWindowTitle(self.glfwWindow,uname)
        else:
            glfw.glfwSetWindowTitle(self.glfwFullscreenWindow,uname)
    def installCallbacks(self,w):
        glfw.glfwSetWindowRefreshCallback(w,self.redisplay)
        glfw.glfwSetKeyCallback(w, self.__key)
        glfw.glfwSetCursorPosCallback(w, self.__motionfunc)
        glfw.glfwSetMouseButtonCallback(w, self.__mousefunc)
        glfw.glfwSetScrollCallback(w, self.__scroll)
        glfw.glfwSetDropCallback(w, self.__dropfunc)
        glfw.glfwSetWindowPosCallback(w, self.__posfunc)
    def setBgProcess(self,state):
        if state:
            if self.bgThread==None:
                self.bgThread = threading.Thread(target=self.bgdrawthread)
                self.bgThread.daemon = True
                self.bgThread.start()
        self.bgControl.put(state)
    def toggleFullscreen(self):
        if not self._isFull:
            monitors = glfw.glfwGetMonitors()
            m = monitors[0]
            mode = glfw.glfwGetVideoMode(m)
            glfw.glfwWindowHint(glfw.GLFW_RED_BITS, 8)
            glfw.glfwWindowHint(glfw.GLFW_GREEN_BITS, 8)
            glfw.glfwWindowHint(glfw.GLFW_BLUE_BITS, 8)
            glfw.glfwWindowHint(glfw.GLFW_ALPHA_BITS, 8)
            uname = self.windowName().encode("utf-8")
            self.glfwFullscreenWindow = glfw.glfwCreateWindow(mode[0],mode[1],uname,m,self.glfwWindow)
            self.installCallbacks(self.glfwFullscreenWindow)
            glfw.glfwHideWindow(self.glfwWindow)
            glfw.glfwSwapInterval(1)
            self._isFull = True
            self.redisplay()
        else:
            glfw.glfwDestroyWindow(self.glfwFullscreenWindow)
            glfw.glfwShowWindow(self.glfwWindow)
            glfw.glfwSwapInterval(1)
            self._isFull = False
            self.redisplay()
    def bgdrawthread(self):
        try:
            while 1:
                while not self.bgActive:
                    self.bgActive = self.bgControl.get()
                while self.bgActive:
                    glfw.glfwMakeContextCurrent(self.backgroundWindow)
                    self.__bgdraw()
                    try:
                        self.bgActive = self.bgControl.get_nowait()
                    except Queue.Empty:
                        pass
        except:
            import traceback
            print "bgdrawthread exception:"
            traceback.print_exc()
        self.bgThread = None
        print "!!!! bgThread EXITED !!!!"
    def run(self):
        while 1:
            shouldClose = glfw.glfwWindowShouldClose(self.glfwWindow)
            if shouldClose:
                if self.okToExit():
                    break
                else:
                    glfw.glfwSetWindowShouldClose(self.glfwWindow,0)
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
            self.__idle()
        glfw.glfwTerminate()
    def windowName(self):
        return "GLCompute"
    def bgWindowName(self):
        return "GLCompute Background"
    def renderScenes(self):
        for s in self.scenes:
            if not s.hidden:
                s.prepareToRender()
        self.scenesPrepared()
        for s in self.scenes:
            if not s.hidden:
                s.render()
    def scenesPrepared(self):
        pass
    def __bgdraw(self):
        if self.bgsync != None and self.hasSync:
            #print "waiting"
            res = glClientWaitSync(self.bgsync,0,0)
            #print "wait over, result =",res
            if res==GL_TIMEOUT_EXPIRED:
                #print "timeout expired, not qeueing more work"
                return
            #print "next job",time.time()
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        w,h = glfw.glfwGetWindowSize(self.backgroundWindow)
        #print "bgdraw",w,h
        glViewport(0,0,w,h)
        glClearColor(1.0,1.0,0.0,1.0)
        glClear(GL_COLOR_BUFFER_BIT|GL_STENCIL_BUFFER_BIT)
        try:
            self.onBgDraw(w,h)
            if self.hasSync:
                self.bgsync = glFenceSync(GL_SYNC_GPU_COMMANDS_COMPLETE,0)
        except:
            import traceback
            traceback.print_exc()
            return
        #glFlush()
        if not self.hasSync:
            self.bgDrawn = False
        if not self.bgDrawn:
            glfw.glfwSwapBuffers(self.backgroundWindow)
            self.bgDrawn = True
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
        glClear(GL_COLOR_BUFFER_BIT|GL_STENCIL_BUFFER_BIT)
        try:
            self.onDraw(w,h)
        except:
            import traceback
            traceback.print_exc()
            return
        self._frames+=1
    def onFboDraw(self):
        pass
    def onBgDraw(self,w,h):
        pass
    def onDraw(self,width,height):
        pass
    def __posfunc(self,window,x,y):
        if self.bgVisibility:
            glfw.glfwSetWindowPos(self.backgroundWindow,x+128,y+128)
    def __bgprocess(self):
        self.bgVisibility = glfw.glfwGetWindowAttrib(self.backgroundWindow,glfw.GLFW_VISIBLE)
        if not self.bgActive:
            if self.bgVisibility:
                #glfw.glfwHideWindow(self.backgroundWindow)
                pass
            return
        if not self.bgVisibility:
            mx,my = glfw.glfwGetWindowPos(self.glfwWindow)
            glfw.glfwSetWindowPos(self.backgroundWindow,mx+128,mx+128)
            #glfw.glfwShowWindow(self.backgroundWindow)
            #if self._isFull:
            #    glfw.glfwShowWindow(self.glfwFullscreenWindow)
            #else:
            #    glfw.glfwShowWindow(self.glfwWindow)
    def __idle(self):
        self.__bgprocess()
        self.onIdle()
    def redisplay(self,window=None):
        self._drawNeeded = True
    def onIdle(self):
        pass
    def __key(self,window, key, scancode, action, mods):
        # Don't propagate release events
        if action == glfw.GLFW_PRESS or action == glfw.GLFW_REPEAT:
            self.key(key,mods)
    def exit(self):
        pass
    def key(self,k,m):
        if k == self.KEY_ESCAPE:
            glfw.glfwSetWindowShouldClose(self.glfwWindow,1)
        if k == self.KEY_TAB:
            self.toggleFullscreen()
    def okToExit(self):
        return True
    def __scroll(self,window,xoffset,yoffset):
        self.onScroll(xoffset,yoffset)
    def onScroll(self,x,y):
        pass
    def __mousefunc(self,window,button,action,mods):
        x,y = glfw.glfwGetCursorPos(window)
        if action==glfw.GLFW_PRESS: state = self.BUTTON_DOWN
        else: action = self.BUTTON_UP
        if button==glfw.GLFW_MOUSE_BUTTON_LEFT: button = self.BUTTON_LEFT
        elif button==glfw.GLFW_MOUSE_BUTTON_RIGHT: button = self.BUTTON_RIGHT
        else: return # Don't support middle button
        self.buttons[button] = action
        self.input2d(x,y,self.buttons)
    def __motionfunc(self,window,x,y):
        self.input2d(x,y,self.buttons)
    def input2d(self,x,y,buttons):
        pass
    def setCursorVisible(self,visible):
        #if self.cursorVisible != None:
        #    if visible == self.cursorVisible:
        #        return
        w = self.glfwWindow
        if self._isFull:
            w = self.glfwFullscreenWindow
        if visible: # 3 times as workaround for bug in GLFW
            glfw.glfwSetInputMode(w,glfw.GLFW_CURSOR,glfw.GLFW_CURSOR_NORMAL)
            glfw.glfwSetInputMode(w,glfw.GLFW_CURSOR,glfw.GLFW_CURSOR_HIDDEN)
            glfw.glfwSetInputMode(w,glfw.GLFW_CURSOR,glfw.GLFW_CURSOR_NORMAL)
        else:
            glfw.glfwSetInputMode(w,glfw.GLFW_CURSOR,glfw.GLFW_CURSOR_HIDDEN)
            glfw.glfwSetInputMode(w,glfw.GLFW_CURSOR,glfw.GLFW_CURSOR_NORMAL)
            glfw.glfwSetInputMode(w,glfw.GLFW_CURSOR,glfw.GLFW_CURSOR_HIDDEN)
        self.cursorVisible = visible
    def __dropfunc(self,window,count,objects):
        result = [objects[i] for i in range(count)]
        try:
            self.drop(result)
        except:
            pass
    def drop(self,objects):
        pass
