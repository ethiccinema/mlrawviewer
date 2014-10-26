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

class ScrollBar(ui.Button):
    def __init__(self,width,height,onclick,**kwds):
        super(ScrollBar,self).__init__(width,height,onclick,**kwds)
        self.motionWhileClicked = True
        self.dragging = False
        self.handle = ui.Geometry(svbo=self.svbo)
        self.children.append(self.handle)
    def resize(self,perc,offset):
        if perc>=1.0:
            self.opacity = 0.0
        else:
            self.opacity = 1.0
        self.perc = perc
        self.offset = offset
        self.rectangle(self.size[0],self.size[1],rgba=(0.1,0.1,0.1,0.5))
        self.handle.rectangle(30,self.size[1]*perc,rgba=(0.5,0.5,0.5,0.5))
        self.handle.setPos(5,self.size[1]*offset)
    def event2d(self,lx,ly,buttons):
        if buttons[0] == 1:
            if self.dragging == False:
                self.dragging = True
            # Clicked
            self.onclick(lx,ly)
            return self
        else:
            self.dragging = False
            return None

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
        self.shownpath = None
        self.background = None
        self.upicon = None
        self.closeicon = None
        self.icons = self.frames.icons
        self.iconsz = self.frames.iconsz
        self.icontex = self.frames.icontex
        self.items = None
        self.scrollbar = None
    def key(self,k,m):
        if k==self.frames.KEY_BACKSPACE:
            self.close()
        elif k==self.frames.KEY_UP:
            self.scroll(0,1)
        elif k==self.frames.KEY_DOWN:
            self.scroll(0,-1)
        elif k==self.frames.KEY_PAGE_UP:
            self.scroll(0,8)
        elif k==self.frames.KEY_PAGE_DOWN:
            self.scroll(0,-8)
        elif k==self.frames.KEY_LEFT_SHIFT or k==self.frames.KEY_RIGHT_SHIFT:
            self.upFolder()
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
    def scroll(self,x,y):
        self.layoutcount = 0
        self.yoffset -= y*10
        if self.yoffset < 0: self.yoffset = 0
        if self.yoffset > self.scrollextent: self.yoffset = self.scrollextent
        self.frames.refresh()
    def browse(self,path):
        self.scanJob.join() # Wait for any previous job to complete
        self.scanResults = [] # Delete all old results
        self.reset()
        self.path = path
        self.prompt = "Choose a file to view"
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
        self.layoutsize = None
        self.background = None
        self.upicon = None
        self.closeicon = None
        self.items = None
        self.yoffset = 0
        self.scrollextent = 0
        self.scrollbar = None
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
        folders.sort()
        for d in folders:
            self.scanResults.append((True,os.path.join(root,d),None))
        candidates.sort()
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
                    self.frames.refresh()
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
    def close(self,x=0,y=0):
        self.frames.toggleBrowser()
    def upFolder(self,x=0,y=0):
        up = os.path.split(self.path)[0]
        if len(up)>0 and up != self.path:
            self.browse(up)
    def scrollDrag(self,x,y):
        p = float(y)/float(self.scrollbar.size[1]*(1.0-self.scrollbar.perc))
        if p>1.0: p = 1.0
        if p<0.0: p = 0.0
        self.yoffset = p * self.scrollextent
        self.frames.refresh()
    def prepareToRender(self):
        if not self.background:
            self.background = ui.Geometry(svbo=self.svbo)
            self.background.setPos(0,0)
            self.background.rectangle(self.size[0],self.size[1],rgba=(0.25,0.25,0.25,1.0))
            self.drawables.insert(0,self.background)
        if self.size != self.layoutsize:
            self.background.rectangle(self.size[0],self.size[1],rgba=(0.25,0.25,0.25,1.0))
        if not self.title:
            self.title = ui.Text("",svbo=self.svbo)
            self.title.ignoreInput = True
            self.title.maxchars = 200
            self.title.setScale(0.4)
            self.title.setPos(40,25)
            self.title.colour = (1.0,1.0,1.0,1.0)
            self.titlebg = ui.Geometry(svbo=self.svbo)
            self.titlebg.edges = (1.0,1.0,0.01,0.2)
            self.titlebg.setPos(10.0,10.0)
            self.titlebg.rectangle(self.size[0]-20,80,rgba=(0.25,0.25,0.25,0.75))
            self.drawables.append(self.titlebg)
            self.drawables.append(self.title)
        if not self.upicon:
            self.upicon = self.newIcon(0,0,128,128,0,self.upFolder)
            self.upicon.setScale(0.2)
            self.upicon.rotation = 90
            self.upicon.setPos(85,75)
            self.drawables.append(self.upicon)
        if not self.closeicon:
            self.closeicon = self.newIcon(0,0,128,128,33,self.close)
            self.closeicon.setScale(0.35)
            self.closeicon.rotation = 45
            self.closeicon.setPos(15,50)
            self.drawables.append(self.closeicon)
        if self.shownpath != self.path or self.size != self.layoutsize:
            p = self.path
            ps = p
            self.svbo.bind()
            while 1:
                self.title.text = self.prompt+"\n     "+ps
                self.title.update()
                if self.title.size[0]>self.size[0]-105:
                    p = p[1:]
                    ps = "..."+p
                else:
                    break
            self.title.setPos(85,10+40-self.title.size[1]/2)
            self.shownpath = self.path
            self.svbo.upload()
        if not self.items:
            self.items = ui.Geometry(svbo=self.svbo)
            self.items.ignoreMotion = True
            self.items.ignoreInput = False
            self.drawables.insert(1,self.items)
        if not self.scrollbar:
            self.scrollbar = ScrollBar(40,self.size[1]-95,self.scrollDrag,svbo=self.svbo)
            self.scrollbar.edges = (1.0,1.0,0.5,0.02)
            self.drawables.append(self.scrollbar)
        if self.size != self.layoutsize:
            self.scrollbar.size = (40,self.size[1]-95)
            self.scrollbar.setPos(self.size[0]-30,95)
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
                    # Work out how to scale the thumb to preserve original aspect ratio
                    tscale = 240.0/t.shape[1]
                    newy = t.shape[0]*tscale
                    if newy>135:
                        tscale = 135.0/t.shape[0]
                    tscale *= 0.95
                    thumb = ui.Geometry(svbo=self.svbo)
                    item.t = t
                    item.rectangle(240,135,rgba=(0.0,0.0,0.0,1.0))
                    item.edges = (1.0,1.0,0.02,0.05)
                    thumb.rectangle(t.shape[1]*tscale,t.shape[0]*tscale,rgba=(1.0,1.0,1.0,1.0),uv=uv,solid=0.0,tex=1,texture=atlas)
                    thumb.setPos(120-t.shape[1]*tscale*0.5,135*0.5-t.shape[0]*tscale*0.5)
                    item.children.append(thumb)
                    meta = ui.Text(os.path.split(fullpath)[1],svbo=self.svbo)
                    meta.ignoreInput = True
                    meta.maxchars = 80
                    meta.setScale(0.25)
                    meta.colour = (1.0,1.0,1.0,1.0)
                    meta.setPos(10,115)
                    meta.update()
                    metabg = ui.Geometry(svbo=self.svbo)
                    metabg.rectangle(meta.size[0]+10,meta.size[1]+5,rgba=(0.05,0.05,0.05,0.5))
                    metabg.setPos(5,112)
                    item.children.append(metabg)
                    item.children.append(meta)
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
                    name.text = n
                    while 1:
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
                self.items.children.append(item)
                #item.setScale(0.5)
            self.folderitems.sort()
            self.thumbitems.sort()
            self.svbo.upload()
        self.frames.svbo.bind()
        self.layout()
    def layout(self):
        if self.size != self.layoutsize or self.layoutcount != len(self.thumbitems)+len(self.folderitems):
            y = 0
            x = 0
            for fp,item in self.folderitems:
                item.setPos(x,y)
                x += item.size[0]+10
                if x> self.size[0]-item.size[0]-20:
                    x = 0
                    y += item.size[1]+10
            if x!=0:
                x = 0
                y += item.size[1]+10
            for fp,item in self.thumbitems:
                item.setPos(x,y)
                x += item.size[0]+10
                if x> self.size[0]-item.size[0]-20:
                    x = 0
                    y += item.size[1]+10
            if x != 0:
                y += item.size[1]+10
            if item:
                self.items.size = ((item.size[0]+10)*int(self.size[0]/(item.size[0]+10)),y)
        self.scrollextent = self.items.size[1] - (self.size[1] - 100)
        if self.scrollextent < 0: self.scrollextent = 0
        if self.yoffset > self.scrollextent: self.yoffset = self.scrollextent
        self.items.setPos(20,100-self.yoffset)
        self.layoutsize = self.size
        self.layoutcount = len(self.thumbitems)+len(self.folderitems)
        self.titlebg.rectangle(self.size[0]-20,80,rgba=(0.25,0.25,0.25,0.75))
        self.scrollbar.resize(float(self.size[1]-100)/float(self.items.size[1]),self.yoffset/float(self.items.size[1]))
    def render(self):
        self.svbo.bind()
        super(DialogScene,self).render()
        self.frames.svbo.bind()



