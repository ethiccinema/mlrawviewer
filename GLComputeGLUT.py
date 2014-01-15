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

    KEY_A = ord('A')
    KEY_D = ord('D')
    KEY_E = ord('E')
    KEY_Q = ord('Q')
    KEY_T = ord('T')

    KEY_LEFT = 100
    KEY_RIGHT = 102
    KEY_UP = 101
    KEY_DOWN = 103

    def __init__(self,width=640,height=360,**kwds):
        self.width = width  
        self.height = height
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
        glutSpecialFunc(self.__specialkey)
        self._isFull = False
        self._start = time.time()
        self._frames = 0
        self._fps = 25
        self._last = time.time()
        self.scenes = [] # Render these scenes in order
        super(GLCompute,self).__init__(**kwds)
    def toggleFullscreen(self):
        if self._isFull:
            glutReshapeWindow(self.width,self.height)
            self._isFull = False
        else:
            glutFullScreen()
            self._isFull = True
    def run(self):
        glutMainLoop()
    def windowName(self):
        return "GLCompute"
    def renderScenes(self):
        for s in self.scenes:
            s.render(self._frames)
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
        glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
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
    def onDraw(self,width,height):
        pass
    def __idle(self):
        self.onIdle()
    def redisplay(self):
        glutPostRedisplay()
    def onIdle(self):
        pass
    def __close(self):
        try:
            glutLeaveMainLoop()
        except:
            sys.exit(0) # Needed on Mac
    def __key(self,k,x,y):
        k = ord(k)
        # Always map lower case keys to upper case
        if k>=ord('a') and k<=ord('z'):
            k -= ord('a')-ord('A')
        self.key(k)
    def __specialkey(self,k,x,y):
        self.key(k)
    def key(self,k):
        if k==self.KEY_ESCAPE:
            self.__close()
        if k==self.KEY_TAB:
            self.toggleFullscreen()