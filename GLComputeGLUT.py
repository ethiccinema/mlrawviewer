"""
GLComputeGLUT.py
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

"""

# standard python imports. Should not be missing
import sys,urllib,urllib2,json,time

# OpenGL. Could be missing
try:
    from OpenGL.GL import *
    from OpenGL.GLUT import *
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

from datetime import datetime
def timeInUsec():
    dt = datetime.now()
    return dt.day*3600.0*24.0+dt.hour*3600.0+dt.minute*60.0+dt.second+0.000001*dt.microsecond

class GLCompute(object):
    KEY_ESCAPE = 27
    KEY_TAB = 9
    KEY_SPACE = 32
    KEY_PERIOD = ord('.')
    KEY_COMMA = ord(',')
    KEY_ZERO = ord('0')
    KEY_ONE = ord('1')
    KEY_TWO = ord('2')
    KEY_THREE = ord('3')
    KEY_FOUR = ord('4')
    KEY_FIVE = ord('5')
    KEY_SIX = ord('6')
    KEY_SEVEN = ord('7')
    KEY_EIGHT = ord('8')
    KEY_NINE = ord('9')

    KEY_A = ord('A')
    KEY_B = ord('B')
    KEY_C = ord('C')
    KEY_D = ord('D')
    KEY_E = ord('E')
    KEY_F = ord('F')
    KEY_G = ord('G')
    KEY_H = ord('H')
    KEY_I = ord('I')
    KEY_J = ord('J')
    KEY_K = ord('K')
    KEY_L = ord('L')
    KEY_M = ord('M')
    KEY_N = ord('N')
    KEY_O = ord('O')
    KEY_P = ord('P')
    KEY_Q = ord('Q')
    KEY_R = ord('R')
    KEY_S = ord('S')
    KEY_T = ord('T')
    KEY_U = ord('U')
    KEY_V = ord('V')
    KEY_W = ord('W')
    KEY_X = ord('X')
    KEY_Y = ord('Y')
    KEY_Z = ord('Z')

    KEY_BACKSPACE = 8

    KEY_LEFT = 100
    KEY_RIGHT = 102
    KEY_UP = 101
    KEY_DOWN = 103
    KEY_PAGE_UP = 104
    KEY_PAGE_DOWN = 105

    KEY_LEFT_SHIFT = 112
    KEY_RIGHT_SHIFT = 113

    KEY_MOD_SHIFT = GLUT_ACTIVE_SHIFT
    KEY_MOD_CONTROL = GLUT_ACTIVE_CTRL
    KEY_MOD_ALT = GLUT_ACTIVE_ALT

    BUTTON_DOWN = 1
    BUTTON_UP = 0
    BUTTON_LEFT = 0
    BUTTON_RIGHT = 1

    def __init__(self,width=640,height=360,**kwds):
        self.width = width  
        self.height = height
        self.windowX = 0
        self.windowY = 0
        glutInit(sys.argv) 
        glutInitDisplayMode(GLUT_DOUBLE|GLUT_RGB|GLUT_STENCIL)
        glutInitWindowSize(256,16)
        glutInitWindowPosition(0,0)
        self.backgroundWindow = glutCreateWindow(self.bgWindowName())
        self.bgDrawn = False
        self.bgActive = False
        self.bgVisibility = 0
        glutDisplayFunc(self.__bgdraw)
        glutVisibilityFunc(self.__bgvisble)
        glutInitWindowSize(width,height)
        glutInitDisplayMode(GLUT_DOUBLE|GLUT_RGB|GLUT_STENCIL)
        self.mainWindow = glutCreateWindow(self.windowName())
        glutSetWindowTitle(self.windowName())  
        glutDisplayFunc(self.__draw)
        glutMouseFunc(self.__mousefunc)
        glutMotionFunc(self.__motionfunc)
        glutPassiveMotionFunc(self.__passivemotionfunc)
        glutIdleFunc(self.__idle)
        try: 
            glutCloseFunc(self.__close)
            glutSetOption(GLUT_ACTION_ON_WINDOW_CLOSE,GLUT_ACTION_GLUTMAINLOOP_RETURNS)
        except:
            pass # Hmm... doesn't work on Mac
        glutKeyboardFunc(self.__key)
        glutSpecialFunc(self.__specialkey)
        self._isFull = False
        self._start = time.time()
        self._frames = 0
        self._fps = 25
        self._last = time.time()
        self.scenes = [] # Render these scenes in order
        self.buttons = [self.BUTTON_UP,self.BUTTON_UP]
        self.bgsync = None
        try:
            self.hasSync = glFenceSync
            self.hasSync = False# True - Doesn't work on Mac/Win
        except:
            self.hasSync = False
        super(GLCompute,self).__init__(**kwds)
    def setBgProcess(self,state):
        self.bgActive = state
    def toggleFullscreen(self):
        if self._isFull:
            glutReshapeWindow(self.width,self.height)
            self._isFull = False
        else:
            glutFullScreen()
            self._isFull = True
        self.setCursorVisible(True)
    def run(self):
        glutMainLoop()
    def updateWindowName(self):
        glutSetWindowTitle(self.windowName())
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
    def __bgvisble(self,state):
        if state!=GLUT_NOT_VISIBLE:
            self.bgDrawn = False
            self.bgVisibility = state
    def __bgdraw(self):
        glutSetWindow(self.backgroundWindow)
        if self.bgsync != None and self.hasSync:
            #print "waiting"
            res = glClientWaitSync(self.bgsync,0,0)
            #print "wait over, result =",res
            if res==GL_TIMEOUT_EXPIRED:
                #print "timeout expired, not qeueing more work"
                glutSetWindow(self.mainWindow)
                return
            #print "next job",time.time()
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        glutReshapeWindow(256,16)
        w = glutGet(GLUT_WINDOW_WIDTH)
        h = glutGet(GLUT_WINDOW_HEIGHT)
        #print "bgdraw",w,h
        glViewport(0,0,w,h)
        glClearColor(0.0,0.0,0.0,1)
        glClear(GL_COLOR_BUFFER_BIT|GL_STENCIL_BUFFER_BIT)
        try:
            self.onBgDraw(w,h)
            if self.hasSync:
                self.bgsync = glFenceSync(GL_SYNC_GPU_COMMANDS_COMPLETE,0)
        except:
            import traceback
            traceback.print_exc()
            glutLeaveMainLoop()
            return    
        #glFlush()
        if not self.hasSync:
            self.bgDrawn = False
        if not self.bgDrawn:
            glutSwapBuffers()
            self.bgDrawn = True
        glutSetWindow(self.mainWindow)
    def __draw(self):
        self._last = timeInUsec()
        self.onFboDraw()
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        w = glutGet(GLUT_WINDOW_WIDTH)
        h = glutGet(GLUT_WINDOW_HEIGHT)
        if not self._isFull:
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
            glutLeaveMainLoop()
            return    
        glutSwapBuffers()
        self._frames+=1
    def onFboDraw(self):
        pass
    def onBgDraw(self,width,height):
        pass
    def onDraw(self,width,height):
        pass
    def __bgprocess(self):
        if not self.bgActive:
            if self.bgVisibility != GLUT_NOT_VISIBLE:
                glutSetWindow(self.backgroundWindow)
                glutHideWindow()
                glutSetWindow(self.mainWindow)
            return
        mx = glutGet(GLUT_WINDOW_X)
        my = glutGet(GLUT_WINDOW_Y)
        glutSetWindow(self.backgroundWindow)
        if self.bgVisibility==GLUT_NOT_VISIBLE:
            glutDisplayFunc(self.__bgdraw)
            glutShowWindow()
            glutPushWindow()
        glutReshapeWindow(256,16)
        x = glutGet(GLUT_WINDOW_X)
        y = glutGet(GLUT_WINDOW_Y)
        if x!=mx or y!=my:
            glutPositionWindow(mx+128,my+128)
        glutPostRedisplay()
        glutSetWindow(self.mainWindow)
    def __idle(self):
        self.__bgprocess()
        #glutShowWindow()
        self.onIdle()
    def redisplay(self):
        glutPostRedisplay()
    def onIdle(self):
        pass
    def okToExit(self):
        return True
    def __close(self):
        if not self.okToExit(): return
        self.exit()
        try:
            glutLeaveMainLoop()
        except:
            sys.exit(0) # Needed on Mac
    def exit(self):
        pass
    def __key(self,k,x,y):
        k = ord(k)
        # Always map lower case keys to upper case
        if k>=ord('a') and k<=ord('z'):
            k -= ord('a')-ord('A')
        m = glutGetModifiers()
        self.key(k,m)
    def __specialkey(self,k,x,y):
        m = glutGetModifiers()
        self.key(k,m)
    def key(self,k,m):
        if k==self.KEY_ESCAPE:
            self.__close()
        if k==self.KEY_TAB:
            self.toggleFullscreen()
    def __mousefunc(self,button,state,x,y):
        if state==GLUT_DOWN: state = self.BUTTON_DOWN
        else: state = self.BUTTON_UP
        if button==GLUT_LEFT_BUTTON: button = self.BUTTON_LEFT
        elif button==GLUT_RIGHT_BUTTON: button = self.BUTTON_RIGHT
        else: return # Don't support middle button
        self.buttons[button] = state
        self.input2d(x,y,self.buttons)
    def __motionfunc(self,x,y):
        self.input2d(x,y,self.buttons)
    def __passivemotionfunc(self,x,y):
        self.input2d(x,y,self.buttons)
    def input2d(self,x,y,buttons):
        print "input2d",x,y,buttons
    def setCursorVisible(self,visible):
        if visible:
            glutSetCursor(GLUT_CURSOR_INHERIT)
        else:
            glutSetCursor(GLUT_CURSOR_NONE)
    def drop(self,objects):
        pass
