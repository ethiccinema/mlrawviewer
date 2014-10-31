"""
Prompt.py, part of MlRawViewer
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
"""

import zlib,os,sys,math,time,threading,Queue

from Config import config

import PerformanceLog
from PerformanceLog import PLOG
PLOG_FILE_IO = PerformanceLog.PLOG_TYPE(0,"FILE_IO")
PLOG_FRAME = PerformanceLog.PLOG_TYPE(1,"FRAME")
PLOG_CPU = PerformanceLog.PLOG_TYPE(2,"CPU")
PLOG_GPU = PerformanceLog.PLOG_TYPE(3,"GPU")

import GLCompute
import GLComputeUI as ui
import ExportQueue
from ShaderText import *
import MlRaw
import LUT

programpath = os.path.abspath(os.path.split(sys.argv[0])[0])

class PromptScene(ui.Scene):
    def __init__(self,frames,**kwds):
        super(PromptScene,self).__init__(**kwds)
        self.frames = frames
        self.svbo = ui.SharedVbo()
        self.background = None
        self.upicon = None
        self.closeicon = None
        self.icons = self.frames.icons
        self.iconsz = self.frames.iconsz
        self.icontex = self.frames.icontex
        self.items = None
        self.title = None
        self.titlebg = None
        self.layoutsize = (0,0)
    def key(self,k,m):
        if k==self.frames.KEY_BACKSPACE:
            self.close()
        elif k==self.frames.KEY_ENTER:
            self.accept()
        else:
            return False
        return True
    def newIcon(self,x,y,w,h,idx,cb):
        icon = ui.Button(w,h,cb,svbo=self.svbo) # ,onhover=self.updateTooltip,onhoverobj=tip)
        self.setIcon(icon,w,h,idx)
        icon.setPos(x,y)
        icon.colour = (1.0,1.0,1.0,1.0)
        icon.idx = idx
        return icon
    def setIcon(self,icon,w,h,idx):
        ix = idx%(self.iconsz/128)
        iy = idx/(self.iconsz/128)
        s = 128.0/float(self.iconsz)
        icon.rectangle(w,h,uv=(ix*s,iy*s,s,s),solid=0.0,tex=0.0,tint=0.0,texture=self.icontex)
    def reset(self):
        # Clear all old items
        self.svbo.reset()
        self.drawables = []
        self.background = None
        self.upicon = None
        self.closeicon = None
        self.items = None
        self.title = None
        self.titlebg = None
    def close(self,x=0,y=0):
        self.frames.togglePrompt()
    def accept(self,x=0,y=0):
        self.frames.close()
    def makeButton(self,colour,text,onclick):
        b = ui.Button(0,0,svbo=self.svbo,onclick=onclick)
        b.edges = (1.0,1.0,0.2,0.5)
        bt = ui.Text(text,svbo=self.svbo)
        bt.ignoreInput = True
        bt.maxchars = 200
        bt.setScale(0.4)
        bt.update()
        b.size = (bt.size[0]+40,bt.size[1]+40)
        b.children.append(bt)
        b.rectangle(b.size[0],b.size[1],rgba=colour)
        bt.setPos(b.size[0]/2-bt.size[0]/2,b.size[1]/2-bt.size[1]/2)
        return b
    def prepareToRender(self):
        if not self.background:
            self.background = ui.Geometry(svbo=self.svbo)
            self.background.setPos(0,0)
            self.drawables.insert(0,self.background)
        if self.size != self.layoutsize:
            self.background.rectangle(self.size[0],self.size[1],rgba=(0.25,0.25,0.25,0.75))
        if not self.title:
            self.title = ui.Text("",svbo=self.svbo)
            self.title.ignoreInput = True
            self.title.maxchars = 200
            self.title.setScale(0.4)
            self.title.setPos(40,25)
            self.title.colour = (1.0,1.0,1.0,1.0)
            self.titlebg = ui.Geometry(svbo=self.svbo)
            self.titlebg.edges = (1.0,1.0,0.2,0.5)
            self.acceptb = self.makeButton((0.5,0.0,0.0,1.0),"Exit anyway\n(Key: ENTER)",self.accept)
            self.cancelb = self.makeButton((0.0,0.5,0.0,1.0),"Do not exit\n(Key: BACKSPACE)",self.close)
            self.drawables.append(self.titlebg)
            self.drawables.append(self.title)
            self.drawables.append(self.acceptb)
            self.drawables.append(self.cancelb)
        if self.size != self.layoutsize:
            self.title.text = "Exit while exporting in progress?"
            self.title.update()
            self.title.setPos(self.size[0]/2-self.title.size[0]/2,self.size[1]/2-self.title.size[1]-60)
            self.titlebg.setPos(self.title.pos[0]-20,self.title.pos[1]-20)
            self.titlebg.rectangle(self.title.size[0]+40,self.title.size[1]+40,rgba=(0.25,0.25,0.25,0.75))
            self.cancelb.setPos(self.size[0]/2-self.cancelb.size[0]/2,self.titlebg.pos[1]+self.titlebg.size[1]+70)
            self.acceptb.setPos(self.size[0]/2-self.acceptb.size[0]/2,self.titlebg.pos[1]+self.titlebg.size[1]+60+self.acceptb.size[1])
            self.svbo.bind()
            self.svbo.upload()
        self.frames.svbo.bind()
        self.layout()
    def layout(self):
        if self.size != self.layoutsize:
            self.layoutsize = self.size
    def render(self):
        self.svbo.bind()
        super(PromptScene,self).render()
        self.frames.svbo.bind()



