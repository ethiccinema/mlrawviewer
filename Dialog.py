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

programpath = os.path.abspath(os.path.split(sys.argv[0])[0])

class DialogScene(ui.Scene):
    def __init__(self,frames,**kwds):
        super(DialogScene,self).__init__(**kwds)
        self.frames = frames
        self.svbo = ui.SharedVbo()
        self.thumbitems = []
        self.layoutsize = (0,0)
        self.layoutcount = 0
        self.atlases = []
        self.scanJob = Queue.Queue()
        self.scanResults = []
        self.scanThread = threading.Thread(target=self.scanFunction)
        self.scanThread.daemon = True
        self.scanThread.start()
        self.yoffset = 0
    def key(self,k,m):
        if k==self.frames.KEY_BACKSPACE:
            self.frames.toggleBrowser()
        elif k==self.frames.KEY_UP:
            self.scroll(0,1)
        elif k==self.frames.KEY_DOWN:
            self.scroll(0,-1)
        else:
            return False
        return True
    def scroll(self,x,y):
        self.layoutcount = 0
        self.yoffset -= y*10
        if self.yoffset < 0: self.yoffset = 0
        self.frames.refresh()
    def browse(self,path):
        self.scanJob.join() # Wait for any previous job to complete
        self.scanResults = [] # Delete all old results
        self.reset()
        self.scanJob.put(path)
    def reset(self):
        # Clear all old items
        self.svbo.reset()
        self.drawables = []
        self.thumbitems = []
        for atlas in self.atlases:
            atlas.free()
        self.atlases = []
    def scanFunction(self):
        while 1:
            scandir = self.scanJob.get()
            self.findMlv(scandir)
            self.scanJob.task_done()
            self.frames.refresh()
    def indexFile(self,filename):
        r = MlRaw.loadRAWorMLV(filename,preindex=False)
        r.preloadFrame(1)
        r.close()
        t = r.nextFrame()[1].thumb()
        return t
    def findMlv(self,root):
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
                self.scanResults.append((fullpath,t))
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
            atlas = GLCompute.Texture((1024,1024),rgbadata=np.zeros(shape=(1024,1024,3),dtype=np.uint16),hasalpha=False,mono=False,sixteen=True,mipmap=False)
            self.atlases.append(atlas)
            index = atlas.atlasadd(thumbnail.flatten(),thumbnail.shape[1],thumbnail.shape[0])
        uv = atlas.atlas[index]
        return index,atlas,uv
    def prepareToRender(self):
        if len(self.scanResults)>0:
            self.svbo.bind()
            while 1:
                try:
                    ft = self.scanResults.pop()
                except:
                    break
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
                item.fp = fullpath
                self.thumbitems.append((fullpath,item))
            self.thumbitems.sort()
            self.svbo.upload()
            self.frames.svbo.bind()
        self.layout()
    def layout(self):
        if self.size != self.layoutsize or self.layoutcount != len(self.thumbitems):
            y = 100-self.yoffset
            x = 100
            for fp,item in self.thumbitems:
                item.setPos(x,y)
                x += item.t.shape[1]+10
                if x> self.size[0]-item.t.shape[1]:
                    x = 100
                    y += item.t.shape[0]+10
            self.layoutsize = self.size
            self.laoucount = len(self.thumbitems)
    def render(self):
        self.svbo.bind()
        super(DialogScene,self).render()
        self.frames.svbo.bind()



