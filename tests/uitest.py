#!/usr/bin/python2.7


# standard python imports. Should not be missing
import sys,struct,os,math,time,datetime,zlib,random

# So we can use modules from the main dir
root = os.path.split(sys.path[0])[0]
sys.path.append(root)

# OpenGL. Could be missing
try:
    from OpenGL.GL import *
    from OpenGL.GL.framebufferobjects import *
except Exception,err:
    print """There is a problem with your python environment.
I Could not import the pyOpenGL module.
On Debian/Ubuntu try "sudo apt-get install python-opengl"
"""
    sys.exit(1)

# numpy. Could be missing
try:
    import numpy as np
except Exception,err:
    print """There is a problem with your python environment.
I Could not import the numpy module.
On Debian/Ubuntu try "sudo apt-get install python-numpy"
"""
    sys.exit(1)

# Now import our own modules
import GLCompute
import GLComputeUI as ui
import Font
from ShaderText import *
from Matrix import *

class Viewer(GLCompute.GLCompute):
    def __init__(self,**kwds):
        super(Viewer,self).__init__(width=960,height=540,**kwds)
        self._init = False
        self.font = Font.Font(os.path.join(root,"data/os.glf"))
        self.icons = zlib.decompress(file(os.path.join(root,"data/icons.z"),'rb').read())
        self.iconsz = int(math.sqrt(len(self.icons)))
        self.timeline = ui.Timeline()
        self.timeline.setNow(time.time())
        self.svbo = ui.SharedVbo()
        self.wasFull = False
        self.keyfocus = None
    def onIdle(self):
        self.redisplay()
    def windowName(self):
        return "UI test"
    def boxClick(self,lx,ly):
        if self.box.colour[0]==1.0:
            self.box.colour = (0.0,0.0,1.0,1.0)
        else:
            self.box.colour = (1.0,0.0,1.0,1.0)
    def updateAnims(self):
        if self.iconAnim.progress()>=1.0:
            targr = random.random()*360.0
            dur = random.random()
            delay = random.random()
            interp = ui.Animation.LINEAR
            if random.random()>0.5:
                interp = ui.Animation.SMOOTH 
            self.iconAnim.setTarget(targr,dur,delay,interp)
    def init(self):
        if self._init: return
        #self.offset = self.svbo.allocate(6*12*4*50)
        self.svbo.bind()
        self.iconAnim = ui.Animation(self.timeline)
        self.fonttex = GLCompute.Texture((1024,1024),rgbadata=self.font.atlas,hasalpha=False,mono=True,sixteen=False,mipmap=True)
        self.icontex = GLCompute.Texture((self.iconsz,self.iconsz),rgbadata=self.icons,hasalpha=False,mono=True,sixteen=False,mipmap=True)
        self.shader = ShaderText(self.font)
        self.matrix = Matrix4x4()
        self.pos = (0.0,0.0)
        self.left = 0.0
        self.right = 0.0
        self.scene = ui.Scene()
        self.scenes.append(self.scene)
        
        self.box = ui.Button(100,100,self.boxClick,svbo=self.svbo)
        self.box.rectangle(100,100,rgba=(1.0,1.0,1.0,1.0))
        self.box.edges = (1.0,1.0,0.1,0.25)
        self.box.setPos(400,200)
        self.childbox = ui.Geometry(svbo=self.svbo)
        self.childbox.rectangle(50,50,rgba=(1.0,1.0,1.0,1.0))
        self.childbox.colour = (0.0,1.0,0.0,0.5)
        self.childbox.setTransformOffset(25.0,25.0)
        self.childbox.setPos(50.0,50.0)
        self.childbox.edges = (1.0,1.0,0.1,0.1)
        self.hw = ui.Text(text="Hello World!",svbo=self.svbo)
        self.hw.setScale(1.0)
        self.hw.update()
        
        self.iconitems = []
        for i in range(5):
            # Icons
            icon = ui.Geometry(svbo=self.svbo)
            ix = i%(self.iconsz/128)
            iy = i/(self.iconsz/128)
            s = 128.0/float(self.iconsz)
            r = icon.rectangle(128.0,128.0,uv=(ix*s,iy*s,s,s),solid=0.0,tex=0.0,tint=0.0,texture=self.icontex)
            icon.setPos(64.0+i*200.0,64.0+i*20.0)
            icon.colour = (0.5*(float(i+1)%2.0),0.333*(float(i+1)%3.0),0.25*(float(i+1)%4.0),1.0)
            icon.setTransformOffset(64.0,64.0)
            self.scene.drawables.append(icon)
            self.iconitems.append(icon)
        self.childbox.children.append(self.hw)
        self.box.children.append(self.childbox)
        self.scene.drawables.append(self.box)

        self.flicker = ui.Flickable(400,200,svbo=self.svbo)
        self.scene.drawables.append(self.flicker)
        self.flicker.rectangle(400,200,rgba=(0.5,0.5,0.5,0.5))
        self.flicker.colour = (1.0,1.0,1.0,0.5)
        self.flicker.setPos(500.0,300.0)
        #self.flicker.allowx = False
        self.canvas = ui.Geometry(self.svbo)
        self.canvas.size = (1000,1000)
        self.flicker.children.append(self.canvas)
        self.cliptest = ui.Text(text="Am I clipped? I certainly hope so.\nThis is the second line.\nHello! I'm the third line.\nThis is number 4.\nI'm 5.\nAnd I'm 6.\nI'm only 7.",svbo=self.svbo)
        self.cliptest.setScale(1.0)
        self.cliptest.update()
        self.cliptest.ignoreInput = True
        self.canvas.size = self.cliptest.size
        self.cliptest.setTransformOffset(0.0,0.0)
        self.cliptest.setPos(0.0,0.0)
        self.clipbut = ui.Button(100,100,self.clipbutClick,svbo=self.svbo)
        self.clipbut.rectangle(100,100,rgba=(1.0,1.0,1.0,1.0))
        self.clipbut.colour = (1.0,1.0,0.0,1.0)
        self.clipbut.edges = (1.0,1.0,0.1,0.25)
        self.clipbut.setPos(100,200)
        self.flicker.clip = True
        self.canvas.children.append(self.cliptest)
        self.canvas.children.append(self.clipbut)

        self.svbo.upload()
        self._init = True
    def clipbutClick(self,x,y):
        print "clip",x,y

    def onDraw(self,width,height):
        self.init()
        if self._isFull != self.wasFull:
            GLCompute.SharedContextState.reset_state()
            self.svbo.bound = False
            self.wasFull = self._isFull
            self.svbo.bind()
        self.timeline.setNow(time.time())
        self.updateAnims()
        self.hw.update()
        self.iconitems[1].setRotation(self.iconAnim.value())
        self.scene.setSize(width,height)

        self.box.setRotation(self.box.rotation - 0.1)
        #self.cliptest.setRotation(self.box.rotation*10 - 0.1)
        #self.flicker.setRotation(-self.box.rotation - 0.1)

        self.svbo.upload() # In case there are changes
        """
        self.childbox.rotation += 1.0
        for index,icon in enumerate(self.iconitems):
            icon.rotation += (1.0+float(index))*0.2
        """
        self.renderScenes()
    def input2d(self,x,y,buttons):
        #print "input2d",x,y,buttons
        handled = self.scene.input2d(x,y,buttons)
        if handled: return
        #self.hw.setPos(200,400)
        if buttons[self.BUTTON_LEFT]==self.BUTTON_DOWN: self.left = 1.0
        else: self.left = 0.0
        if buttons[self.BUTTON_RIGHT]==self.BUTTON_DOWN: self.right = 1.0
        else: self.right = 0.0
        #self.box.setScale(1.0+self.left+self.right)
    def key(self,k,m):
        if self.keyfocus:
            self.keyfocus = self.keyfocus.key(k,m)
        else:
            self.keyfocus = self.hw.key(k,m)
        if not self.keyfocus:
            super(Viewer,self).key(k,m) # Inherit standard behaviour
    def drop(self,objects):
        print "Dropped",objects
 
def main(): 
    rmc = Viewer()   
    return rmc.run()

if __name__ == '__main__':
    sys.exit(main())
