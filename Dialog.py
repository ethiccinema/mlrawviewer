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
        self.folderitems = []
        self.layoutsize = (0,0)
        self.layoutcount = 0
        self.atlases = []
        self.scanJob = Queue.Queue()
        self.scanResults = []
        self.scanThread = threading.Thread(target=self.scanFunction)
        self.scanThread.daemon = True
        self.scanThread.start()
        self.thumbcache = {}
        self.yoffset = 0
        self.title = None
        self.path = ""
    def key(self,k,m):
        if k==self.frames.KEY_BACKSPACE:
            self.frames.toggleBrowser()
        elif k==self.frames.KEY_UP:
            self.scroll(0,1)
        elif k==self.frames.KEY_DOWN:
            self.scroll(0,-1)
        elif k==self.frames.KEY_PAGE_UP:
            self.scroll(0,8)
        elif k==self.frames.KEY_PAGE_DOWN:
            self.scroll(0,-8)
        elif k==self.frames.KEY_LEFT_SHIFT or k==self.frames.KEY_RIGHT_SHIFT:
            self.browse(os.path.split(self.path)[0])
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
        self.path = path
        self.scanJob.put(path)
    def reset(self):
        # Clear all old items
        self.svbo.reset()
        self.drawables = []
        self.title = None
        self.thumbitems = []
        self.folderitems = []
        for atlas in self.atlases:
            atlas.free()
        self.atlases = []
        self.layoutcount = 0
    def scanFunction(self):
        while 1:
            scandir = self.scanJob.get()
            self.find(scandir)
            self.scanJob.task_done()
            self.frames.refresh()
    def indexFile(self,filename):
        r = MlRaw.loadRAWorMLV(filename,preindex=False)
        if r.frames()>1:
            r.preloadFrame(1)
            t = r.nextFrame()[1].thumb()
        else:
            t = r.firstFrame.thumb()
        r.close()
        return t
    def find(self,root):
        try:
            candidates = MlRaw.candidatesInDir(os.path.join(root,"dummy"))
        except:
            candidates = []
        try: 
            folders = [d for d in os.listdir(root) if os.path.isdir(os.path.join(root,d)) and d not in candidates and d[0]!='.' and d[0]!='$']
        except:
            folders = []
        for d in folders:
            self.scanResults.append((True,os.path.join(root,d),None))
        for name in candidates:
            try:
                fullpath = os.path.join(root,name)
                if fullpath in self.thumbcache:
                    t = self.thumbcache[fullpath]
                else:
                    t = self.indexFile(fullpath)
                    if t != None:
                        self.thumbcache[fullpath] = t
                if t != None:
                    self.scanResults.append((False,fullpath,t))
            except:
                import traceback
                traceback.print_exc()
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
        if not self.title:
            self.title = ui.Text("",svbo=self.svbo)
            self.title.ignoreInput = True
            self.title.maxchars = 80
            self.title.setScale(0.5)
            self.title.setPos(40,35)
            self.title.colour = (1.0,1.0,1.0,1.0)
            self.titlebg = ui.Geometry(svbo=self.svbo)
            self.titlebg.edges = (1.0,1.0,0.01,0.2)
            self.titlebg.setPos(10.0,10.0)
            self.titlebg.rectangle(self.size[0]-20,80,rgba=(0.25,0.25,0.25,0.75))
            self.drawables.append(self.titlebg)
            self.drawables.append(self.title)

        if self.title.text != self.path:
            self.title.text = self.path
            self.svbo.bind()
            self.title.update()
            self.svbo.upload()
        if len(self.scanResults)>0:
            self.svbo.bind()
            while 1:
                try:
                    ft = self.scanResults.pop()
                except:
                    break
                isdir,fullpath,t = ft
                if not isdir:
                    index,atlas,uv = self.addToAtlas(t)
                    class entry:
                        def __init__(self,item,frames):
                            self.frames = frames
                            self.item = item
                        def click(self,lx,ly):
                            self.frames.toggleBrowser()
                            self.frames.load(self.item)
                    e = entry(fullpath,self.frames)
                    item = ui.Button(240,135,svbo=self.svbo,onclick=e.click)
                    item.edges = (1.0,1.0,.0,.0)
                    item.colour = (1.0,1.0,1.0,1.0)
                    item.t = t
                    item.rectangle(240,135,rgba=(1.0,1.0,1.0,1.0),uv=uv,solid=0.0,tex=1,texture=atlas)
                    self.thumbitems.append((fullpath,item))
                else:
                    class folder:
                        def __init__(self,item,browser):
                            self.browser = browser
                            self.item = item
                        def click(self,lx,ly):
                            self.browser.browse(self.item)
                    f = folder(fullpath,self)
                    item = ui.Button(240,60,svbo=self.svbo,onclick=f.click)
                    item.edges = (1.0,1.0,.02,.1)
                    item.colour = (1.0,1.0,0.3,1.0)
                    item.rectangle(240,60,rgba=(1.0,1.0,0.3,1.0))
                    name = ui.Text("",svbo=self.svbo)
                    name.ignoreInput = True
                    name.maxchars = 80
                    name.setScale(0.25)
                    name.colour = (0.0,0.0,0.0,1.0)
                    name.size = (220,50)
                    n = os.path.split(fullpath)[1]
                    while 1:
                        name.text = n
                        name.update()
                        if name.size[0]>220:
                            n = n[:-1]
                            name.text = n+"..."
                        else:
                            break
                    name.setPos(120-name.size[0]/2,32-name.size[1]/2)
                    item.children.append(name)
                    self.folderitems.append((fullpath,item))
                item.fp = fullpath
                self.drawables.insert(0,item)
                #item.setScale(0.5)
            self.folderitems.sort()
            self.thumbitems.sort()
            self.svbo.upload()
        self.frames.svbo.bind()
        self.layout()
    def layout(self):
        if self.size != self.layoutsize or self.layoutcount != len(self.thumbitems)+len(self.folderitems):
            y = 100-self.yoffset
            x = 20
            for fp,item in self.folderitems:
                item.setPos(x,y)
                x += item.size[0]+10
                if x> self.size[0]-item.size[0]:
                    x = 20
                    y += item.size[1]+10
            if x!=20:
                x = 20
                y += item.size[1]+10
            for fp,item in self.thumbitems:
                item.setPos(x,y)
                x += item.size[0]+10
                if x> self.size[0]-item.size[0]:
                    x = 20
                    y += item.size[1]+10
            self.layoutsize = self.size
            self.layoutcount = len(self.thumbitems)+len(self.folderitems)
            self.titlebg.rectangle(self.size[0]-20,80,rgba=(0.25,0.25,0.25,0.75))
    def render(self):
        self.svbo.bind()
        super(DialogScene,self).render()
        self.frames.svbo.bind()



