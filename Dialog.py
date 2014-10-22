"""
Dialog.py, part of MlRawViewer
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

import zlib,os,sys,math,time

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

programpath = os.path.abspath(os.path.split(sys.argv[0])[0])

class DialogScene(ui.Scene):
    def __init__(self,frames,**kwds):
        super(DialogScene,self).__init__(**kwds)
        self.frames = frames
        self.svbo = ui.SharedVbo()
        self.init = True
        self.thumbs = []
        self.thumbitems = []
        self.layoutsize = (0,0)
        self.atlases = []
    def indexFile(self,filename):
        r = MlRaw.loadRAWorMLV(filename,preindex=False)
        r.preloadFrame(1)
        r.close()
        t = r.nextFrame()[1].thumb()
        return t
    def findMlv(self,root):
        print root
        allmlvs = []
        for dirpath,dirnames,filenames in os.walk(root):
            mlvs = [fn for fn in filenames if fn.lower().endswith(".mlv") and fn[0]!="."]
            if len(mlvs)>0:
                for fn in mlvs:
                    fullpath = os.path.join(dirpath,fn)
                    allmlvs.append(fullpath)
        for fullpath in allmlvs:
            try:
                t = self.indexFile(fullpath)
                self.thumbs.append((fullpath,t))
            except:
                import traceback
                traceback-print_exc()
                pass
    def addToAtlas(self,thumbnail):
        atlas = None
        index = None
        if len(self.atlases)>0:
            atlas = self.atlases[-1]
            index = atlas.atlasadd(thumbnail.flatten(),thumbnail.shape[1],thumbnail.shape[0])
        if index == None: # Atlas is full or there isn't one yet
            atlas = GLCompute.Texture((2048,2048),rgbadata=np.zeros(shape=(2048,2048,3),dtype=np.uint16),hasalpha=False,mono=False,sixteen=True,mipmap=False)
            self.atlases.append(atlas)
            index = atlas.atlasadd(thumbnail.flatten(),thumbnail.shape[1],thumbnail.shape[0])
        uv = atlas.atlas[index]
        return index,atlas,uv
    def prepareToRender(self):
        if self.init:
            self.findMlv(os.path.abspath(os.path.expanduser("/media/andrew/Shared")))
            self.findMlv(os.path.abspath(os.path.expanduser("~/Videos")))
            self.svbo.bind()
            for ft in self.thumbs:
                fullpath,t = ft
                index,atlas,uv = self.addToAtlas(t)
                class entry:
                    def __init__(self,item,frames):
                        self.frames = frames
                        self.item = item
                    def click(self,lx,ly):
                        print self.item,lx,ly
                        self.frames.toggleBrowser()
                        self.frames.load(self.item)
                e = entry(fullpath,self.frames)
                item = ui.Button(t.shape[1],t.shape[0],svbo=self.svbo,onclick=e.click)
                item.edges = (1.0,1.0,.0,.0)
                item.colour = (1.0,1.0,1.0,1.0)
                self.drawables.append(item)
                item.rectangle(t.shape[1],t.shape[0],rgba=(1.0,1.0,1.0,1.0),uv=uv,solid=0.0,tex=1,texture=atlas)
                #item.setScale(0.5)
                item.t = t
                self.thumbitems.append(item)
            self.svbo.upload()
            self.frames.svbo.bind()
            self.init = False
        self.layout()
    def layout(self):
        if self.size != self.layoutsize:
            y = 100
            x = 100
            for item in self.thumbitems:
                item.setPos(x,y)
                x += item.t.shape[1]+10
                if x> self.size[0]-item.t.shape[1]:
                    x = 100
                    y += item.t.shape[0]+10
            self.layoutsize = self.size
    def render(self):
        self.svbo.bind()
        super(DialogScene,self).render()
        self.frames.svbo.bind()



