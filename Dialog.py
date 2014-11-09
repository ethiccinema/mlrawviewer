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

import zlib,os,sys,math,time,threading,Queue,random

import scandir

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
if config.isWin():
	import psutil

LUT1D = LUT.LUT1D
LUT3D = LUT.LUT3D

programpath = os.path.abspath(os.path.split(sys.argv[0])[0])

SCAN_VIDEOS = 1
SCAN_EXPORT = 2
SCAN_LUT = 3

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

def isNumber(string):
    try:
        number = int(string)
        return True
    except ValueError:
        return False

class DialogScene(ui.Scene):
    def __init__(self,frames,**kwds):
        super(DialogScene,self).__init__(**kwds)
        self.frames = frames
        self.svbo = ui.SharedVbo(size=4*1024*1024)
        self.thumbitems = []
        self.folderitems = []
        self.layoutsize = (0,0)
        self.layoutcount = 0
        self.layoutwidth = 1
        self.atlases = []
        self.scanJob = Queue.Queue()
        self.scanJobCancel = False
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
        self.focusindex = 0 # FolderItems then ThumbItems
        self.focusitem = None
        self.focusmoved = False # Allow named initial item
        self.shownprompt = ""
        self.startfile = None
        self.scantype = 1
        self.dircache = {}
        self.vidcache = {}
        self.skippaths = {}
        self.initSkippaths()
        self.timeline = ui.Timeline()
        self.folderAnimation = ui.Animation(self.timeline,1.0)
        self.folderAnimation.setTarget(1.0,10.0,0.0,ui.Animation.SMOOTH)
        self.lastRefresh = time.time()
    def initSkippaths(self):
        if config.isWin():
            self.skippaths = {
	        "\Boot":True,
	        "\NVIDIA":True,
	        "\Intel":True,
	        "\Windows":True,
	        "\System Volume Information":True,
	        "\Program Files":True,
	        "\Program Files (x86)":True,
	        "\ProgramData":True,
           }
        elif config.isMac():
            self.skippaths = {
                "/Applications":True,
                "/Extra":True,
                "/Library":True,
                "/Network":True,
                "/System":True,
                "/boot":True,
                "/bin":True,
                "/dev":True,
                "/cores":True,
                "/etc":True,
                "/lib":True,
                "/net":True,
                "/proc":True,
                "/run":True,
                "/proc":True,
                "/private":True,
                "/sys":True,
                "/sbin":True,
                "/tmp":True,
                "/var":True,
                "/usr":True,
                "/Volumes/OS":True,
            }
        else:
            self.skippaths = {
                "/bin":True,
                "/boot":True,
                "/cdrom":True,
                "/dev":True,
                "/etc":True,
                "/lib":True,
                "/lib32":True,
                "/lib64":True,
                "/libx32":True,
                "/lost+found":True,
                "/proc":True,
                "/run":True,
                "/proc":True,
                "/selinux":True,
                "/sys":True,
                "/sbin":True,
                "/srv":True,
                "/tmp":True,
                "/var":True,
                "/usr":True,
                "/usr":True,
                "/usr":True,
                "/usr":True,
                "/usr":True,
            }
    def key(self,k,m):
        if k==self.frames.KEY_BACKSPACE:
            self.close()
        elif k==self.frames.KEY_UP:
            self.scroll(0,-1)
        elif k==self.frames.KEY_DOWN:
            self.scroll(0,1)
        elif k==self.frames.KEY_LEFT:
            self.scroll(1,0)
        elif k==self.frames.KEY_RIGHT:
            self.scroll(-1,0)
        elif k==self.frames.KEY_PAGE_UP:
            self.scroll(0,-3)
        elif k==self.frames.KEY_PAGE_DOWN:
            self.scroll(0,3)
        elif k==self.frames.KEY_LEFT_SHIFT or k==self.frames.KEY_RIGHT_SHIFT:
            self.upFolder()
        elif k==self.frames.KEY_ENTER:
            if self.focusindex < len(self.folderitems):
                fi = self.folderitems[self.focusindex][1]
            else:
                fi = self.thumbitems[self.focusindex-len(self.folderitems)][1]
            fi.onclick(0,0)
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
        self.focusmoved = True
        x = int(x)
        y = int(y)
        if len(self.folderitems)+len(self.thumbitems)==0: return
        # First move the highlight by the desired amount
        if y<0:
            for i in range(abs(y)):
                # Up
                # Missing folders
                missing = self.layoutwidth-len(self.folderitems)%self.layoutwidth
                if self.focusindex >= len(self.folderitems) and self.focusindex-self.layoutwidth < len(self.folderitems):
                    self.focusindex += missing
                    self.focusindex -= self.layoutwidth
                    if self.focusindex>=len(self.folderitems):
                        self.focusindex -= self.layoutwidth
                else:
                    self.focusindex -= self.layoutwidth
                if self.focusindex < 0: self.focusindex = 0
        elif y>0:
            for i in range(y):
                # Down
                missing = self.layoutwidth-len(self.folderitems)%self.layoutwidth
                if self.focusindex < len(self.folderitems) and self.focusindex+self.layoutwidth >= len(self.folderitems):
                    self.focusindex += self.layoutwidth
                    if self.focusindex>=len(self.folderitems):
                        self.focusindex -= missing
                    if self.focusindex<len(self.folderitems):
                        self.focusindex += self.layoutwidth
                else:
                    self.focusindex += self.layoutwidth
                m = len(self.folderitems)+len(self.thumbitems)
                if self.focusindex >= m: self.focusindex = m-1
        if x>0:
            for i in range(abs(x)):
                # Left
                self.focusindex -= 1
                if self.focusindex < 0: self.focusindex = 0
        elif x<0:
            for i in range(abs(x)):
                # Right
                self.focusindex += 1
                m = len(self.folderitems)+len(self.thumbitems)
                if self.focusindex == m: self.focusindex = m-1

        # Then scroll the view to keep the highlight in view
        if self.focusindex < len(self.folderitems):
            fi = self.folderitems[self.focusindex][1]
        else:
            fi = self.thumbitems[self.focusindex-len(self.folderitems)][1]
        self.yoffset = fi.pos[1]-(self.items.size[1]-self.scrollextent)/2
        self.layoutcount = 0
        if self.yoffset < 0: self.yoffset = 0
        if self.yoffset > self.scrollextent: self.yoffset = self.scrollextent
        self.frames.refresh()
    def prepareForNewJob(self):
        self.scanJobCancel = True
        self.scanJob.join() # Wait for any previous job to complete
        self.scanJobCancel = False
        self.scanResults = [] # Delete all old results
    def newpath(self,path,filename=None):
        if self.scantype == SCAN_EXPORT:
            config.setState("targetDir",path)
        elif self.scantype == SCAN_LUT:
            config.setState("lutDir",path)
        elif self.scantype == SCAN_VIDEOS:
            config.setState("directory",path)
        self.prepareForNewJob()
        self.reset()
        self.path = path
        self.startfile = filename
        self.scanJob.put(path)
    def browse(self,path,filename=None):
        self.prepareForNewJob()
        self.reset()
        self.path = path
        self.startfile = filename
        self.prompt = "Choose a file to view"
        config.setState("directory",path)
        self.scantype = SCAN_VIDEOS
        self.scanJob.put(path)
    def importLut(self):
        self.prepareForNewJob()
        self.reset()
        self.path = config.getState("lutDir")
        if self.path == None or not os.path.exists(self.path):
            self.path = os.path.expanduser("~")
        self.prompt = "Select new LUTs to import"
        self.scantype = SCAN_LUT
        self.scanJob.put(self.path)
    def chooseExport(self):
        self.scanResults = [] # Delete all old results
        self.reset()
        self.path = config.getState("targetDir")
        self.prompt = "Choose export target folder"
        if self.path == None or not os.path.exists(self.path):
            self.path = os.path.expanduser("~")
        self.scantype = SCAN_EXPORT
        self.scanJob.put(self.path)
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
        self.focusitem = None
        self.focusindex = 0
        self.focusmoved = False
    def removeThumb(self,filename):
        if filename in self.thumbcache:
            del self.thumbcache[filename]
    def scanFunction(self):
        while 1:
            self.scanJobCancel = False
            scandir = self.scanJob.get()
            try:
                self.find(scandir)
            except:
                import traceback
                traceback.print_exc()
            self.scanJobCancel = False
            self.scanJob.task_done()
            self.frames.refresh()
    def indexFile(self,filename):
        r = MlRaw.loadRAWorMLV(filename,preindex=False)
        balance = r.getMeta("balance_v1")
        brightness = r.getMeta("brightness_v1")
        if r.frames()>1:
            r.preloadFrame(1)
            t = r.nextFrame()[1].thumb(balance,brightness)
        else:
            t = r.firstFrame.thumb(balance,brightness)
        r.close()
        return t
    def filterVids(self,root,filenames):
        candvid = 0
        mlv = [n for n in filenames if n.lower().endswith(".mlv")]
        for n in mlv: self.vidcache[os.path.join(root,n)] = True
        raw = [n for n in filenames if n.lower().endswith(".raw")]
        rawcount = 0
        for r in raw:
            base = r[:-2]
            rset = [n for n in filenames if n[:-2]==base and isNumber(n[-2:])]
            rset.insert(0,r)
            rset.sort()
            if len(rset)>0:
                lastraw = rset[-1]
                try:
                    lastrawfile = file(os.path.join(root,lastraw),'rb')
                    lastrawfile.seek(-192,os.SEEK_END)
                    footer = lastrawfile.read(4)
                    lastrawfile.close()
                    if footer=="RAWM":
                        rawcount += 1
                        self.vidcache[os.path.join(root,r)] = True
                except:
                    pass
        dng = [n for n in filenames if n.lower().endswith(".dng")]
        candvid += len(mlv) + rawcount
        if len(dng)>1:
            self.vidcache[root] = True # This dir is possible CDNG
            candvid += 1
        return candvid
    def candidatesInTree(self,path):
        pathnodrive = os.path.splitdrive(path)[1]
	print pathnodrive
        if pathnodrive in self.skippaths:
	    print "skipping",pathnodrive
            return (0,0)
        cacheresults = self.dircache.get(path,None)
        if cacheresults!=None:
            return cacheresults
        self.dircache[path] = (0,0)
        for dirpath,dirnames,filenames in scandir.walk(path,topdown=False):
            candvid = 0
            candlut = 0
            for sd in dirnames:
                sv,sl = self.dircache.setdefault(os.path.join(dirpath,sd),(0,0))
                candvid += sv
                candlut += sl
            candvid += self.filterVids(dirpath,filenames)
            cube = [n for n in filenames if n.lower().endswith(".cube")]
            candlut += len(cube)
            self.dircache[dirpath] = (candvid,candlut)
            if self.scanJobCancel:
                del self.dircache[path]
                return None
        return self.dircache[path]
    def thumbsForFolder(self,folder):
        cached = [n for n in self.thumbcache.keys() if n.startswith(folder)]
        results = [self.thumbcache[n] for n in cached]
        return results
    def find(self,root):
        pathnodrive = os.path.splitdrive(root)[1]
	print pathnodrive
        if pathnodrive in self.skippaths: return
        scantype = self.scantype
        candidates = []
        folders = []
        if len(root)>0:
            try:
                if scantype==SCAN_VIDEOS:
                    candidates = MlRaw.candidatesInDir(os.path.join(root,"dummy"))
                elif scantype==SCAN_LUT:
                    candidates=[f for f in os.listdir(root) if f.lower().endswith(".cube")]
            except:
                pass
            try:
                folders = [d for d in os.listdir(root) if os.path.isdir(os.path.join(root,d)) and d not in candidates and d[0]!='.' and d[0]!='$']
            except:
                pass
        else:
            # Windows list drives
            if config.isWin():
                drives = [p.mountpoint for p in psutil.disk_partitions()]
                drives.sort()
                for d in drives:
                    self.scanResults.append((True,d,[],None))
                return
        folders.sort()
        deepscan = []
        for d in folders:
            scanpath = os.path.join(root,d)
            pathnodrive = os.path.splitdrive(scanpath)[1]
	    print pathnodrive
            if pathnodrive in self.skippaths: continue
            if scantype==SCAN_EXPORT:
                self.scanResults.append((True,scanpath,[],candvid))
                continue
            cacheresults = self.dircache.get(scanpath,None)
            if cacheresults!=None:
                candvid,candlut = cacheresults
                if scantype==SCAN_VIDEOS and candvid>0:
                    thumbs = self.thumbsForFolder(scanpath)
                    self.scanResults.append((True,scanpath,thumbs,candvid))
                elif scantype==SCAN_LUT and candlut>0:
                    self.scanResults.append((True,scanpath,[],candlut))
            else:
                deepscan.append(scanpath)
                self.scanResults.append((True,scanpath,[],None))
        self.frames.refresh()
        candidates.sort()
        for name in candidates:
            try:
                fullpath = os.path.join(root,name)
                if fullpath in self.thumbcache:
                    t = self.thumbcache[fullpath]
                else:
                    if scantype==SCAN_VIDEOS:
                        t = self.indexFile(fullpath)
                    elif scantype==SCAN_LUT:
                        l = LUT.LutCube()
                        l.load(fullpath)
                        exists = False
                        if l.dim()==1:
                            for el in LUT1D:
                                 if el[0].t == l.t:
                                    exists = True
                        elif l.dim()==3:
                            for el in LUT3D:
                                 if el[0].t == l.t:
                                    exists = True
                        if exists: continue
                        t = np.zeros(shape=(90,160,3),dtype=np.uint16)*65535
                        t[:,:,0] += np.linspace(0,65535,90*160).reshape(90,160)
                        t[:,:,1] += np.linspace(0,65535*90,90*160).reshape(90,160)
                        t[:,:,2] += 32768
                    if t != None:
                        self.thumbcache[fullpath] = t
                if t != None:
                    self.scanResults.append((False,fullpath,t,None))
                    self.frames.refresh()
                if self.scanJobCancel:
                    return
            except:
                import traceback
                traceback.print_exc()
                continue
        self.frames.refresh()
        # All essential folders and thumbs are now on screen. Can peacefully deepscan directories
        # So any non-relevant ones can be ignored in future
        deepscan.append(os.path.split(root)[0])
        for scanpath in deepscan:
            self.dircache[scanpath] = (0,0)
            for dirpath,dirnames,filenames in scandir.walk(scanpath):
                # Bottom up so can prune subtrees we cached previously
                candvid = 0
                candlut = 0
                for sd in dirnames:
                    svsl = self.candidatesInTree(os.path.join(scanpath,sd))
                    if svsl == None or self.scanJobCancel:
                        del self.dircache[scanpath]
                        return # Cancelled early
                    sv,sl = svsl
                    candvid += sv
                    candlut += sl
                del dirnames[:]
                candvid += self.filterVids(dirpath,filenames)
                cube = [n for n in filenames if n.lower().endswith(".cube")]
                candlut += len(cube)
                self.dircache[dirpath] = (candvid,candlut)
        # Now we have the full tree from here, load one new thumbnail for every folder in the root. Update the scan results
        vids = self.vidcache.keys()
        for d in folders:
            scanpath = os.path.join(root,d)
            pathnodrive = os.path.splitdrive(scanpath)[1]
	    print pathnodrive
            if pathnodrive in self.skippaths: continue
            cacheresults = self.dircache.get(scanpath,None)
            if cacheresults!=None:
                candvid,candlut = cacheresults
                if scantype==SCAN_VIDEOS and candvid>0:
                    thumbcands = [n for n in vids if n.startswith(scanpath) and n not in self.thumbcache] # Vids in the tree that are not cached
                    if len(thumbcands)>0:
                        newfile = random.choice(thumbcands)
                        newthumb = self.indexFile(newfile)
                        self.thumbcache[newfile] = newthumb
                        thumbs = self.thumbsForFolder(scanpath)
                        self.scanResults.append((True,scanpath,thumbs,candvid))

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
        drive,path = os.path.split(self.path)
        if (drive==self.path) and (len(drive)>0) and (drive!="/"):
            # We are on windows at the root of a drive. Must next list all drives
            self.newpath("",drive)
            return
        up = os.path.split(self.path)[0]
        if len(up)>0 and up != self.path:
            self.newpath(up,os.path.split(self.path)[1])
    def scrollDrag(self,x,y):
        p = float(y)/float(self.scrollbar.size[1]*(1.0-self.scrollbar.perc))
        if p>1.0: p = 1.0
        if p<0.0: p = 0.0
        self.yoffset = p * self.scrollextent
        # Now find the item corresponding to this offset
        count = 0
        #print self.yoffset,self.scrollextent,self.yoffset+(self.items.size[1]-self.scrollextent)/2
        items = self.folderitems + self.thumbitems
        for ifi in items:
            i,fi = ifi
            #print fi.pos,
            if fi.pos[1] > self.yoffset+(self.items.size[1]-self.scrollextent)/3:
                self.focusindex = count
                #print fi,fi.pos[1],self.focusindex
                break
            count += 1
        self.frames.refresh()
    def makeThumb(self,thumbs):
        ti,(index,atlas,uv) = random.choice(thumbs)
        tscale = 240.0/ti.shape[1]
        thumb = ui.Geometry(svbo=self.svbo)
        thumb.size = (ti.shape[1]*tscale,ti.shape[0]*tscale)
        thumb.rectangle(thumb.size[0],thumb.size[1],rgba=(1.0,1.0,1.0,1.0),uv=uv,solid=0.0,tex=1,texture=atlas)
        return thumb
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
        if self.shownpath != self.path or self.size != self.layoutsize or self.prompt != self.shownprompt:
            p = self.path
            ps = p
            self.svbo.bind()
            while 1:
                self.title.text = self.prompt+"\n     "+ps
                self.shownprompt = self.prompt
                self.title.update()
                if self.title.size[0]>self.size[0]-105:
                    p = p[1:]
                    ps = "..."+p
                    if len(p)==0: break
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
        if not self.focusitem:
            self.focusitem = ui.Geometry(svbo=self.svbo)
            self.focusitem.ignoreMotion = True
            self.focusitem.ignoreInput = False
            self.focusitem.edges = (1.0,1.0,0.05,0.05)
            self.focusitem.setPos(10.0,10.0)
            self.items.children.insert(0,self.focusitem)

        if len(self.scanResults)>0:
            self.svbo.bind()
            start = time.time()
            class entry:
                def __init__(self,fullpath,frames,browser):
                    self.frames = frames
                    self.fullpath = fullpath
                    self.browser = browser
                def click(self,lx,ly):
                    if self.browser.scantype==SCAN_VIDEOS:
                        self.browser.scanJobCancel = True
                        self.frames.load(self.fullpath)
                        self.frames.toggleBrowser()
                    elif self.browser.scantype==SCAN_LUT and self.item.opacity==1.0:
                        self.frames.importLut([self.fullpath])
                        self.item.opacity = 0.5
                        self.frames.refresh()
            class folder:
                def __init__(self,item,browser):
                    self.browser = browser
                    self.item = item
                def click(self,lx,ly):
                    self.browser.newpath(self.item)
            while 1:
                try:
                    ft = self.scanResults.pop(0)
                except:
                    break
                isdir,fullpath,t,cand = ft
                additem = True
                if not isdir:
                    index,atlas,uv = self.addToAtlas(t)

                    e = entry(fullpath,self.frames,self)
                    item = ui.Button(240,135,svbo=self.svbo,onclick=e.click)
                    e.item = item
                    item.fullpath = fullpath
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
                    name = os.path.split(fullpath)[1]
                    meta = ui.Text("",svbo=self.svbo)
                    meta.ignoreInput = True
                    meta.maxchars = len(name)
                    meta.setScale(0.25)
                    meta.colour = (1.0,1.0,1.0,1.0)
                    meta.setPos(10,115)
                    meta.text = name
                    while 1:
                        meta.update()
                        if meta.size[0]>220:
                            name = name[:-1]
                            meta.text = name+"..."
                            if len(name)==0: break
                        else:
                            break
                    meta.update()
                    metabg = ui.Geometry(svbo=self.svbo)
                    metabg.rectangle(meta.size[0]+10,meta.size[1]+5,rgba=(0.05,0.05,0.05,0.5))
                    metabg.setPos(5,112)
                    item.children.append(metabg)
                    item.children.append(meta)
                    self.thumbitems.append((fullpath,item))
                else:
                    thumbs = []
                    for thumb in t:
                        thumbs.append((thumb,self.addToAtlas(thumb)))
                        #index,atlas,uv = self.addToAtlas(t)
                    # Check if its already visible
                    item = None
                    for folderpath,existingitem in self.folderitems:
                        if folderpath==fullpath:
                            item=existingitem
                            item.thumbs = thumbs
                            additem = False
                    if item==None:
                        f = folder(fullpath,self)
                        item = ui.Button(240,60,svbo=self.svbo,onclick=f.click)
                        item.edges = (1.0,1.0,.02,.1)
                        item.colour = (0.0,0.0,0.0,1.0)
                        item.rectangle(240,60,rgba=(0.0,0.0,0.0,1.0))
                        item.clip = True
                        item.thumbs = thumbs
                        item.thumb1 = None
                        item.thumb2 = None
                        name = ui.Text("",svbo=self.svbo)
                        name.ignoreInput = True
                        name.maxchars = 80
                        name.setScale(0.35)
                        name.size = (220,50)
                        item.name = name
                        item.name.colour = (1.0,1.0,1.0,1.0)
                        item.namebg = ui.Geometry(svbo=self.svbo)
                        item.namebg.edges = (1.0,1.0,.1,.4)
                    n = os.path.split(fullpath)[1]
                    if len(n)==0:
                        n = os.path.splitdrive(fullpath)[0]
                        try:
                            import win32api
                            vol = win32api.GetVolumeInformation(n+"\\")
                            n += " ("+vol[0]+")"
                        except:
                            pass
                    if cand!=None:
                        item.name.text = n+" (%d)"%cand
                    else:
                        item.name.text = n
                    while 1:
                        item.name.update()
                        if item.name.size[0]>220:
                            n = n[:-1]
                            if cand!=None:
                                item.name.text = n+" (%d)..."%cand
                            else:
                                item.name.text = n+"..."
                            if len(n)==0: break
                        else:
                            break
                    item.name.setPos(120-item.name.size[0]/2,32-item.name.size[1]/2)
                    item.namebg.rectangle(item.name.size[0]+20,item.name.size[1]+10,rgba=(0.05,0.05,0.05,0.5))
                    item.namebg.setPos(120-(item.name.size[0]+20)/2,32-(item.name.size[1]+10)/2)
                    if len(thumbs)>0 and item.thumb1==None:
                        thumb = self.makeThumb(thumbs)
                        item.thumb1 = thumb
                        item.children.append(thumb)
                        thumb = self.makeThumb(thumbs)
                        item.thumb2 = thumb
                        item.children.append(thumb)
                        item.children.append(item.namebg)
                        item.children.append(item.name)
                    elif len(thumbs)==0:
                        item.children.append(item.namebg)
                        item.children.append(item.name)
                    if additem:
                        self.folderitems.append((fullpath,item))
                item.fp = fullpath
                if additem:
                    self.items.children.append(item)
                #item.setScale(0.5)
            self.folderitems.sort()
            self.thumbitems.sort()
            self.svbo.upload()
        self.frames.svbo.bind()
        self.layout()
        # Animation of folder thumbs
        self.lastRefresh = time.time()
        self.timeline.setNow(self.lastRefresh)
        prog = self.folderAnimation.progress()
        swap = False
        if prog>=1.0:
            self.folderAnimation.targval = 0.0
            self.folderAnimation.setTarget(1.0,10.0,0.0,ui.Animation.SMOOTH)
            swap = True
        prog = self.folderAnimation.progress()
        t1p = prog*0.5+0.5
        t2p = prog*0.5
        for fullpath,item in self.folderitems:
            if item.thumb1 and len(item.thumbs)>0:
                if swap:
                    del item.children[0]
                    item.thumb1 = item.thumb2
                    item.thumb2 = self.makeThumb(item.thumbs)
                    item.children.insert(1,item.thumb2)
                item.thumb1.setPos(0,-(t1p)*(item.thumb1.size[1]-60))
                item.thumb2.opacity = (t2p*4.0)
                if item.thumb2.opacity>1.0: item.thumb2.opacity = 1.0
                item.thumb2.setPos(0,-(t2p)*(item.thumb2.size[1]-60))
    def layout(self):
        if self.size != self.layoutsize or self.layoutcount != len(self.thumbitems)+len(self.folderitems):
            y = 0
            x = 0
            c = 0
            itemnum = 0
            item = None
            lw = None
            for fp,item in self.folderitems:
                item.setPos(x,y)
                x += item.size[0]+10
                c += 1
                if x> self.size[0]-item.size[0]-20:
                    x = 0
                    y += item.size[1]+10
                    if lw == None and c>0: lw = c
                if not self.focusmoved and os.path.split(fp)[1]==self.startfile:
                    self.focusindex = itemnum
                itemnum += 1
            if x!=0:
                x = 0
                y += item.size[1]+10
            for fp,item in self.thumbitems:
                item.setPos(x,y)
                x += item.size[0]+10
                c += 1
                if x> self.size[0]-item.size[0]-20:
                    x = 0
                    y += item.size[1]+10
                    if lw == None and c>0: lw = c
                if not self.focusmoved and os.path.split(fp)[1]==self.startfile:
                    self.focusindex = itemnum
                itemnum += 1
            if x != 0:
                y += item.size[1]+10
            if item:
                self.items.size = ((item.size[0]+10)*int(self.size[0]/(item.size[0]+10)),y)
            if lw != None:
                self.layoutwidth = lw
        self.titlebg.rectangle(self.size[0]-20,80,rgba=(0.25,0.25,0.25,0.75))
        if self.items.size[1]>0:
            self.scrollbar.resize(float(self.size[1]-100)/float(self.items.size[1]),self.yoffset/float(self.items.size[1]))
        # Position the focus item
        self.scrollextent = self.items.size[1] - (self.size[1] - 100)
        if self.scrollextent < 0: self.scrollextent = 0
        fi = None
        if (len(self.folderitems)+len(self.thumbitems))>0:
            if self.focusindex < len(self.folderitems):
                fi = self.folderitems[self.focusindex][1]
            else:
                fi = self.thumbitems[self.focusindex-len(self.folderitems)][1]
            self.focusitem.rectangle(fi.size[0]+10,fi.size[1]+10,rgba=(0.5,0.5,0.0,0.5))
            self.focusitem.setPos(fi.pos[0]-5,fi.pos[1]-5)
            self.yoffset = fi.pos[1]-(self.items.size[1]-self.scrollextent)/2
        if self.yoffset < 0: self.yoffset = 0
        if self.yoffset > self.scrollextent: self.yoffset = self.scrollextent
        self.items.setPos(20,100-self.yoffset)
        self.layoutsize = self.size
        self.layoutcount = len(self.thumbitems)+len(self.folderitems)

    def render(self):
        self.svbo.bind()
        super(DialogScene,self).render()
        self.frames.svbo.bind()



