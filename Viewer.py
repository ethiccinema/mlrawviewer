"""
Viewer.py, part of MlRawViewer
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

import subprocess,wave

from Config import config

import PerformanceLog
from PerformanceLog import PLOG
PerformanceLog.PLOG_CONTROL(False)
PLOG_FILE_IO = PerformanceLog.PLOG_TYPE(0,"FILE_IO")
PLOG_FRAME = PerformanceLog.PLOG_TYPE(1,"FRAME")
PLOG_CPU = PerformanceLog.PLOG_TYPE(2,"CPU")
PLOG_GPU = PerformanceLog.PLOG_TYPE(3,"GPU")

import MlRaw
import GLCompute
import GLComputeUI as ui
import ExportQueue
from Matrix import *
from Demosaicer import *
from Display import *
from Audio import *
import LUT
from Dialog import *

ENCODE_TYPE_MOV = 0
ENCODE_TYPE_DNG = 1
ENCODE_TYPE_MAX = 2

LUT1D = LUT.LUT1D
LUT3D = LUT.LUT3D

class Viewer(GLCompute.GLCompute):
    def __init__(self,**kwds):
        userWidth = 800
        self.colourUndoStack = []
        self.colourRedoStack = []
        self.vidAspectHeight = 9.0/16.0
        self.vidAspectWidth = 16.0/9.0
        self.raw = None
        super(Viewer,self).__init__(width=userWidth,height=int(userWidth*self.vidAspectHeight),**kwds)
        self._init = False
        self.icons = None
        self.display = None
        self.realStartTime = 0
        self.playTime = 0
        self.playFrameNumber = 0
        self.nextFrameNumber = 0
        self.neededFrame = 0
        self.drawnFrameNumber = None
        self.playFrame = None #self.raw.firstFrame
        self.frameCache = {} # {0:self.raw.firstFrame}
        self.preloadingFrame = []
        self.preloadingFrames = []
        #self.preloadFrame(1) # Immediately try to preload the next frame
        self.paused = False
        self.needsRefresh = False
        self.anamorphic = False # Canon squeeze
        self.anamorLens = 0 # Lens squeeze
        self.encoderProcess = None
        self.outfilename = config.getState("targetDir")
        self.lastEncodedFrame = None
        self.demosaicCount = 0
        self.demosaicTotal = 0.0
        self.demosaicAverage = 0.0
        self.audio = Audio()
        self.wavname = None # wavfilename
        self.wav = None
        self.indexing = True
        #self.audioOffset = self.raw.getMeta("audioOffset_v1")
        #if self.audioOffset == None: self.audioOffset = 0.0
        self.lastEventTime = time.time()
        self.hideOverlay = False
        self.wasFull = False
        self.demosaic = None
        self.dialog = None
        self.browser = False
        #self.markLoad()
        # Shared settings
        #self.initFps()
        self.setting_rgb = (2.0, 1.0, 1.5)
        self.setting_highQuality = False
        self.setting_encoding = False
        self.setting_tonemap = 8 # 0 = Linear, 1 = Global tone map, 2 = Log, 3 = sRGB Gamma, 4 = Rec.709 Gamma, 5 = SLoggmma, 6 = SLog2gamma, 7 = LogCgamma, 8 = CLoggamma
        self.setting_dropframes = True # Real time playback by default
        self.setting_loop = config.getState("loopPlayback")
        self.setting_colourMatrix = np.matrix(np.eye(3))
        self.setting_preprocess = config.getState("preprocess")
        if self.setting_preprocess == None:
	        self.setting_preprocess = False
        #self.updateColourMatrix()
        if self.setting_loop == None: self.setting_loop = True
        self.setting_encodeType = config.getState("encodeType")
        if self.setting_encodeType == None: self.setting_encodeType = (ENCODE_TYPE_MOV,)
        self.setting_histogram = config.getState("histogramType")
        if self.setting_histogram == None: self.setting_histogram = 0
        self.svbo = None
        self.svbostatic = None
        self.fpsMeasure = None
        self.fpsCount = 0

        self.exporter = ExportQueue.ExportQueue(config)
        self.wasExporting = False
        self.exportActive = False
        self.exportLastStatus = 0.0
        self.toggleEncoding() # On by default
        self.lut3dindex = 0
        self.lut1d1index = 0
        self.lut1d2index = 0

    def initFps(self):
        self.fps = self.raw.fps
        self.setting_fpsOverride = self.raw.getMeta("fpsOverride_v1")
        if self.setting_fpsOverride != None:
            self.fps = self.setting_fpsOverride

    def openBrowser(self,initFolder=None):
        if initFolder==None:
            initFolder = config.getState("directory")
            if not os.path.exists(initFolder):
                initFolder = None
            if initFolder == None:
                initFolder = '~'
            initFolder = os.path.expanduser(initFolder)
        self.init()
        self.dialog.browse(initFolder)
        self.dialog.hidden = False
        self.browser = True

    def load(self,newname):
        print "Loading",repr(newname)
        try:
            r = MlRaw.loadRAWorMLV(newname)
        except:
            import traceback
            traceback.print_exc()
        self.loadSet(r,newname)

    def loadNewRawSet(self,step):
        fn = self.raw.filename
        path,name = os.path.split(fn) # Correct for files and CDNG dirs
        if len(name)==0:
            path,name = os.path.split(path)
        fl = MlRaw.candidatesInDir(fn)
        #print self.raw.filename,fl,path,name
        current = fl.index(name)
        newOne = (current + step)%len(fl)
        found = False
        while not found:
            newname = os.path.join(path,fl[newOne])
            print "Loading",repr(newname)
            try:
                r = MlRaw.loadRAWorMLV(newname)
                found = True
            except:
                pass
            newOne = (newOne + step)%len(fl)
        self.loadSet(r,newname)

    def loadSet(self,raw,newname):
        self.wavname = newname[:-3]+"WAV"

        # Hack to load any WAV file we find in a DNG dir
        if os.path.isdir(newname) or newname.lower().endswith(".dng"):
            wavdir = os.path.split(newname)[0]
            if os.path.isdir(newname):
                wavdir = newname
            wavfiles = [w for w in os.listdir(wavdir) if w.lower().endswith(".wav")]
            if len(wavfiles)>0:
                self.wavname = os.path.join(wavdir,wavfiles[0])
        self.colourUndoStack = []
        self.colourRedoStack = []
        self.audio.stop()
        if self.demosaic:
            self.demosaic.free() # Release textures
        self.wav = None
        if self.raw:
            self.raw.close()
        self.raw = raw
        self.playFrame = self.raw.firstFrame
        self.frameCache = {0:self.raw.firstFrame}
        self.preloadingFrame = []
        self.preloadingFrames = []
        self.realStartTime = 0
        self.playTime = 0
        self.playFrameNumber = 0
        self.nextFrameNumber = 0
        self.neededFrame = 0
        self.initFps()
        self.audioOffset = self.raw.getMeta("audioOffset_v1")
        if self.audioOffset == None: self.audioOffset = 0.0
        self.drawnFrameNumber = None
        self.preloadFrame(1) # Immediately try to preload the next frame
        self.indexing = True
        self.markLoad()
        self._init = False
        self.init()
        self.updateWindowName()
        self.updateColourMatrix()
        if self.paused:
            self.togglePlay() # Play..
        self.refresh()

    def drop(self,objects):
        # Drag and drop from the system! Not drop-frames
        fn = objects[0]
        print fn
        if fn.lower().endswith(".wav"):
            self.loadWav(fn)
        else:
            r = MlRaw.loadRAWorMLV(fn)
            if r:
                self.loadSet(r,fn)

    def loadWav(self,wavname):
        self.audio.stop()
        self.wav = None
        self.wavname = wavname
        self.initWav()
        if not self.paused:
            self.togglePlay() # Pause..
            self.togglePlay() # ...and restart with new Wav

    def windowName(self):
        if self.raw:
            return "MlRawViewer v"+config.versionString()+" - "+self.raw.description()
        else:
            return "MlRawViewer v"+config.versionString()

    def init(self):
        if self._init: return
        if self.icons == None:
            self.icons = zlib.decompress(file(os.path.join(programpath,"data/icons.z"),'rb').read())
            self.iconsz = int(math.sqrt(len(self.icons)))
            self.icontex = GLCompute.Texture((self.iconsz,self.iconsz),rgbadata=self.icons,hasalpha=False,mono=True,sixteen=False,mipmap=True)
        if self.svbo == None:
            self.svbo = ui.SharedVbo()
        if self.svbostatic == None:
            self.svbostatic = ui.SharedVbo(size=16*1024*1024)
        self.scenes = []
        if self.demosaic == None and self.raw:
            self.demosaic = DemosaicScene(self.raw,self,self,self,size=(self.raw.width(),self.raw.height()))
        elif self.demosaic:
            self.demosaic.initTextures()
            self.demosaic.setSize(self.raw.width(),self.raw.height())
        if self.demosaic:
            self.scenes.append(self.demosaic)
        if self.display == None and self.raw:
            self.display = DisplayScene(self,size=(0,0))
        if self.display:
            self.display.setRgbImage(self.demosaic.rgbImage)
            self.display.setHistogram(self.demosaic.histogramTex)
            self.scenes.append(self.display)
        if self.dialog == None:
            self.dialog = DialogScene(self,size=(0,0))
            self.dialog.hidden = True
        self.scenes.append(self.dialog)
        self.initWav()
        if self.raw:
            self.vidAspectHeight = float(self.raw.height())/(self.raw.width()) # multiply this number on width to give height in aspect
            self.vidAspectWidth = float(self.raw.width())/(self.raw.height()) # multiply this number on height to give height in aspect
        else:
            self.vidAspectHeight = 9.0/16.0
            self.vidAspectWidth = 16.0/9.0
        self._init = True
    def onDraw(self,width,height):
        # First convert Raw to RGB image at same size
        PLOG(PLOG_FRAME,"onDraw start")
        self.init()
        if self._isFull != self.wasFull:
            GLCompute.SharedContextState.reset_state()
            self.svbo.bound = False
            self.wasFull = self._isFull
        if not self.svbo.bound:
            self.svbo.bind()
        if self.raw:
            if self.realStartTime == None or self.raw.indexingStatus()<1.0:
                offset = self.playFrameNumber / self.fps
                self.realStartTime = time.time() - offset
                PLOG(PLOG_FRAME,"realStartTime set to %f"%self.realStartTime)
            aspectHeight = int((width*self.vidAspectHeight))
            aspectWidth = int((height*self.vidAspectWidth))
            if self.anamorphic == True:
                aspectHeight = int(aspectHeight*1.6)
                aspectWidth = int(aspectWidth/1.6)
            if self.anamorLens != 0:
                if self.anamorLens == 1:
                    aspectHeight = int(aspectHeight/(4.0/3))
                    aspectWidth = int(aspectWidth*(4.0/3))
                elif self.anamorLens == 2:
                    aspectHeight = int(aspectHeight/1.4)
                    aspectWidth = int(aspectWidth*1.4)
                elif self.anamorLens == 3:
                    aspectHeight = int(aspectHeight/1.5)
                    aspectWidth = int(aspectWidth*1.5)
                elif self.anamorLens == 4:
                    aspectHeight = int(aspectHeight/2.0)
                    aspectWidth = int(aspectWidth*2.0)
            if height > aspectHeight:
                self.display.setSize(width,aspectHeight)
                self.display.setPosition(0, height/2 - aspectHeight/2)
            else:
                self.display.setSize(aspectWidth,height)
                self.display.setPosition(width/2 - aspectWidth/2, 0)
        self.dialog.setSize(width,height)
        self.dialog.setPosition(0,0)
        self.renderScenes()
        if self.raw:
            self.drawnFrameNumber = self.playFrameNumber
            if self.paused: # or self.raw.indexingStatus()<1.0:
                self._frames -= 1
            if self.raw.indexingStatus()<1.0:
                self.refresh()
        PLOG(PLOG_FRAME,"onDraw end")
    def scenesPrepared(self):
        self.svbo.upload() # In case there are changes
    def jumpTo(self,frameToJumpTo):
        #if self.raw.indexingStatus()==1.0:
        if frameToJumpTo<0:
            frameToJumpTo = 0
        if frameToJumpTo>=self.raw.frames():
            frameToJumpTo = self.raw.frames()

        now = time.time()
        self.realStartTime = now - frameToJumpTo / self.fps
        self.neededFrame = int(frameToJumpTo)
        self.nextFrameNumber = int(frameToJumpTo) # For non-frame dropping case
        self.audio.stop()
        if not self.paused:
            offset = now - self.realStartTime
            self.startAudio(offset)
        PLOG(PLOG_FRAME,"jump to %d frame, now need %d"%(frameToJumpTo,self.neededFrame))
        self.refresh()
    def jump(self,framesToJumpBy):
        #if self.raw.indexingStatus()==1.0:
        if framesToJumpBy<0 and (-framesToJumpBy) > self.neededFrame:
            framesToJumpBy = -self.neededFrame # Should only go to start
        if (self.neededFrame + framesToJumpBy) >= self.raw.frames():
            framesToJumpBy = self.raw.frames() - self.neededFrame - 1

        self.realStartTime -= framesToJumpBy / self.fps
        self.neededFrame += int(framesToJumpBy)
        self.nextFrameNumber += int(framesToJumpBy) # For non-frame dropping case
        self.audio.stop()
        if not self.paused:
            now = time.time()
            offset = now - self.realStartTime
            self.startAudio(offset)
        PLOG(PLOG_FRAME,"jump by %d frames, now need %d"%(framesToJumpBy,self.neededFrame))
        self.refresh()
    def onScroll(self,x,y):
        if self.browser:
            self.dialog.scroll(x,y)
        else:
            if x<0:
                self.jump(self.fps*0.5) # Go back 1 second (will wrap)
            elif x>0:
                self.jump(-self.fps*0.5) # Go forward 1 second (will wrap)
            """
            if y<0:
                self.scaleBrightness(1.1)
            elif y>0:
                self.scaleBrightness(1.0/1.1)
            """

    def key(self,k,m):
        if self.browser:
            # Defer processing to browser view
            if not self.dialog.key(k,m):
                super(Viewer,self).key(k,m) # Inherit standard behaviour
            return

        now = time.time()
        if (now - self.lastEventTime)>5.0:
            self.refresh()
        self.lastEventTime = now
        if k==self.KEY_SPACE:
            self.togglePlay()
        elif k==self.KEY_PERIOD: # Nudge forward one frame - best when paused
            self.jump(1)
        elif k==self.KEY_COMMA: # Nudge back on frame - best when paused
            self.jump(-1)


        elif k==self.KEY_ZERO:
            self.toggleStripes()

        elif k==self.KEY_ONE:
            if m==0:
                self.changeWhiteBalance(2.0, 1.0, 2.0, "WhiteFluro")  # ~WhiteFluro
            elif m==1:
                self.deleteLut1D()
        elif k==self.KEY_TWO:
            self.changeWhiteBalance(2.0, 1.0, 1.5, "Daylight")    # ~Daylight
        elif k==self.KEY_THREE:
            if m==0:
                self.changeWhiteBalance(2.5, 1.0, 1.5, "Cloudy ")     # ~Cloudy
            elif m==1:
                self.deleteLut3D()

        elif k==self.KEY_FOUR:
            self.changeWhiteBalance(self.setting_rgb[0]*0.99, self.setting_rgb[1], self.setting_rgb[2], "red-")
        elif k==self.KEY_SEVEN:
            self.changeWhiteBalance(self.setting_rgb[0]*(1.0/0.99), self.setting_rgb[1], self.setting_rgb[2], "red+")
        elif k==self.KEY_SIX:
            self.changeWhiteBalance(self.setting_rgb[0], self.setting_rgb[1], self.setting_rgb[2]*0.99, "blue-")
        elif k==self.KEY_NINE:
            self.changeWhiteBalance(self.setting_rgb[0], self.setting_rgb[1], self.setting_rgb[2]*(1.0/0.99), "blue+")

        # Green control is now done by modifying R/B/brightness together
        elif k==self.KEY_FIVE:
            self.changeWhiteBalance(self.setting_rgb[0]*(1.0/0.99), self.setting_rgb[1], self.setting_rgb[2]*(1.0/0.99), "green-")
            self.scaleBrightness(0.99)
        elif k==self.KEY_EIGHT:
            self.changeWhiteBalance(self.setting_rgb[0]*0.99, self.setting_rgb[1], self.setting_rgb[2]*0.99, "green+")
            self.scaleBrightness(1.0/0.99)

        elif k==self.KEY_Q:
            self.toggleQuality()
        elif k==self.KEY_A:
            self.toggleAnamorphic() #anamorphic for canon squeeze
        elif k==self.KEY_S:
            self.toggleAnamorLens() #anamorphic for lenses
        elif k==self.KEY_E:
            self.addEncoding()
        elif k==self.KEY_C:
            self.addEncodingAll()
        elif k==self.KEY_Y:
            self.toggleEncoding()
        elif k==self.KEY_D:
            self.toggleEncodeType()
        elif k==self.KEY_F:
            if m==0: # No mod
                self.toggleDropFrames()
            elif m==1:
                self.toggleFpsOverride()
        elif k==self.KEY_T:
            if m==0:
                self.toggleToneMapping()
            elif m==1:
                self.toggleToneMapping(reverse=True)
        elif k==self.KEY_L:
            if m==0:
                self.toggleLooping()
            elif m==1:
                self.importLut()

        elif k==self.KEY_G:
            self.loadBalance()
        elif k==self.KEY_H:
            if m==0:
                self.saveBalance()
            else:
                self.changeHistogram()

        # Mark management
        elif k==self.KEY_R:
            self.markReset()
            self.refresh()
        elif k==self.KEY_P:
            self.markNext()
        elif k==self.KEY_U:
            self.markPrev()
        elif k==self.KEY_I:
            self.markIn()
        elif k==self.KEY_O:
            self.markOut()

        elif k==self.KEY_V:
            self.slideAudio(-0.5)
        elif k==self.KEY_B:
            self.slideAudio(-(1.0/float(self.fps)))
        elif k==self.KEY_N:
            self.slideAudio(1.0/(float(self.fps)))
        elif k==self.KEY_M:
            self.slideAudio(0.5)

        elif k==self.KEY_J:
            self.loadNewRawSet(-1)
        elif k==self.KEY_K:
            self.loadNewRawSet(1)

        elif k==self.KEY_W:
            self.toggleChooseExport()
            #self.askOutput()

        elif k==self.KEY_Z:
            if m==0:
                self.exporter.cancelAllJobs()
                self.refresh()
            elif m==1:
                self.changeLut1D2(-1)
        elif k==self.KEY_X:
            if m==0:
                if self.exporter.currentjob != -1:
                    self.exporter.cancelJob(self.exporter.currentjob)
                else:
                    nextjobs = self.exporter.jobs.keys()
                    if len(nextjobs)>0:
                        nextjobs.sort()
                        self.exporter.cancelJob(nextjobs[0])
                self.refresh()
            elif m==1:
                self.changeLut1D2(1)
        elif k==self.KEY_LEFT: # Left cursor
            if m==0:
                self.jump(-self.fps) # Go back 1 second (will wrap)
            elif m==1:
                self.changeLut1D1(-1)
        elif k==self.KEY_RIGHT: # Right cursor
            if m==0:
                self.jump(self.fps) # Go forward 1 second (will wrap)
            elif m==1:
                self.changeLut1D1(1)
        elif k==self.KEY_UP: # Up cursor
            if m==0:
                self.scaleBrightness(1.1)
            elif m==1:
                self.changeLut3D(1)
        elif k==self.KEY_DOWN: # Down cursor
            if m==0:
                self.scaleBrightness(1.0/1.1)
            elif m==1:
                self.changeLut3D(-1)

        elif k==self.KEY_BACKSPACE:
            self.toggleBrowser()

        elif m==1 and k==self.KEY_TAB:
            self.toggleHideOverlay()

        else:
            super(Viewer,self).key(k,m) # Inherit standard behaviour

    def changeHistogram(self):
        self.setting_histogram = (self.setting_histogram + 1)%2
        config.setState("histogramType",self.setting_histogram)

    def currentLut3D(self):
        return self.setting_lut3d
    def currentLut1D1(self):
        return self.setting_lut1d1
    def currentLut1D2(self):
        return self.setting_lut1d2

    def importLut(self):
        result = launchDialog("importLut")
        filenames = result.split("\n")
        update1d = False
        update3d = False
        for f in filenames:
            fn = f.strip()
            l = LUT.LutCube()
            try:
                l.load(fn)
                print "Importing LUT",fn
                if l.dim()==1:
                    LUT1D.append((l,LUT.LUT_USER))
                    update1d = True
                elif l.dim()==3:
                    LUT3D.append((l,LUT.LUT_USER))
                    update3d = True
            except:
		import traceback
		traceback.print_exc()
                pass
        if update1d:
            config.setState("lut1d",LUT1D)
        if update3d:
            config.setState("lut3d",LUT3D)

    def deleteLut3D(self):
        """
        Delete the current LUT3D from the current file, and from the index
        """
        del LUT3D[self.lut3dindex-1]
        config.setState("lut3d",LUT3D)
        self.setting_lut3d = None
        self.lut3dindex = 0
        self.raw.setMeta("lut3d_v1",None)
        self.refresh()

    def deleteLut1D(self):
        """
        Delete the current LUT1D from the current file, and from the index
        """
        if LUT1D[self.lut1d1index-1][1] != LUT.LUT_STANDARD:
            del LUT1D[self.lut1d1index-1]
            config.setState("lut1d",LUT1D)
        self.lut1d1index = 0
        self.setting_lut1d1 = None
        self.raw.setMeta("lut1d1_v1",None)
        self.refresh()

    def changeLut3D(self,change):
        self.lut3dindex += change

        ix = self.lut3dindex%(len(LUT3D)+1)
        if ix == 0:
            self.setting_lut3d = None
            #print "LUT3D disabled"
        else:
            #print "Loading LUT",LUT.LUT_FNS[ix-1]
            self.setting_lut3d = LUT3D[ix-1][0]
        self.raw.setMeta("lut3d_v1",self.setting_lut3d)
        self.refresh()

    def changeLut1D1(self,change):
        self.lut1d1index += change

        ix = self.lut1d1index%(len(LUT1D)+1)
        if ix == 0:
            self.setting_lut1d1 = None
        else:
            self.setting_lut1d1 = LUT1D[ix-1][0]
        self.raw.setMeta("lut1d1_v1",self.setting_lut1d1)
        self.refresh()

    def changeLut1D2(self,change):
        self.lut1d2index += change

        ix = self.lut1d2index%(len(LUT1D)+1)
        if ix == 0:
            self.setting_lut1d2 = None
        else:
            self.setting_lut1d2 = LUT1D[ix-1][0]
        self.raw.setMeta("lut1d2_v1",self.setting_lut1d2)
        self.refresh()

    def userIdleTime(self):
        idleAdd = 0
        if self.hideOverlay: idleAdd += 10.0
        now = time.time()
        return now - self.lastEventTime + idleAdd

    def input2d(self,x,y,buttons):
        now = time.time()
        if self.display != None and not self.display.hidden:
            handled = self.display.input2d(x,y,buttons)
        elif self.dialog != None and not self.dialog.hidden:
            handled = self.dialog.input2d(x,y,buttons)
        if (now - self.lastEventTime)>5.0:
            self.refresh()
        self.lastEventTime = now

    def colourUndo(self):
        if len(self.colourUndoStack)==0: return
        brightness,balance = self.colourUndoStack.pop()
        self.colourRedoStack.append((self.setting_brightness,self.setting_rgb))
        self.setting_brightness = brightness
        self.setting_rgb = balance
        self.raw.setMeta("brightness_v1",self.setting_brightness)
        self.raw.setMeta("balance_v1",self.setting_rgb)
        self.refresh()

    def colourRedo(self):
        if len(self.colourRedoStack)==0: return
        brightness,balance = self.colourRedoStack.pop()
        self.colourUndoStack.append((self.setting_brightness,self.setting_rgb))
        self.setting_brightness = brightness
        self.setting_rgb = balance
        self.raw.setMeta("brightness_v1",self.setting_brightness)
        self.raw.setMeta("balance_v1",self.setting_rgb)
        self.refresh()

    def setBrightness(self,value,updateUndoStack=True):
        if updateUndoStack:
            self.colourRedoStack = []
            self.colourUndoStack.append((self.setting_brightness,self.setting_rgb))
        self.setting_brightness = value
        #print "Brightness",self.setting_brightness
        if updateUndoStack:
            self.raw.setMeta("brightness_v1",self.setting_brightness)
        self.refresh()
    def scaleBrightness(self,scale):
        self.setBrightness(self.setting_brightness * scale)
    def checkMultiplier(self, N, MAX=8.0, MIN=0.0):
        if N > MAX:
            return MAX
        elif N < MIN:
            return MIN
        else:
            return N
    def changeWhiteBalance(self, R, G, B, Name="WB",updateUndoStack=True):
        R = self.checkMultiplier(R)
        G = self.checkMultiplier(G)
        B = self.checkMultiplier(B)
        if updateUndoStack:
            self.colourUndoStack.append((self.setting_brightness,self.setting_rgb))
        self.setting_rgb = (R, G, B)
        if updateUndoStack:
            self.raw.setMeta("balance_v1",self.setting_rgb)
        #print "%s:\t %.1f %.1f %.1f"%(Name, R, G, B)
        if updateUndoStack:
            self.colourRedoStack = []
        self.refresh()
    def toggleHideOverlay(self):
        self.hideOverlay = not self.hideOverlay
        self.refresh()
    def togglePlay(self):
        self.paused = not self.paused
        if self.paused:
            #self.jump(-1) # Redisplay the current frame in high quality
            self.audio.stop()
            self.refresh()
        else:
            if self.playFrameNumber >= (self.raw.frames()-1):
                self.playFrameNumber = 0 # Paused at end, looping probbaly off
                self.nextFrameNumber = 0 # So restart from start
            offset = self.playFrameNumber / self.fps
            self.realStartTime = time.time() - offset
            self.startAudio(offset)
    def toggleQuality(self):
        self.setting_highQuality = not self.setting_highQuality
        self.refresh()
    def toggleStripes(self):
        self.setting_preprocess = not self.setting_preprocess
        config.setState("preprocess",self.setting_preprocess)
        self.refresh()
    def toggleAnamorphic(self):
        self.anamorphic = not self.anamorphic
        self.refresh()
    def toggleAnamorLens(self):
        self.anamorLens = (self.anamorLens + 1)%5
        self.refresh()
    def toggleToneMapping(self,reverse=False):
        if not reverse:
            self.setting_tonemap = (self.setting_tonemap + 1)%9
        else:
            self.setting_tonemap = (self.setting_tonemap - 1)%9
        self.raw.setMeta("tonemap_v1",self.setting_tonemap)
        self.refresh()
    def toggleLooping(self):
        self.setting_loop = not self.setting_loop
        config.setState("loopPlayback",self.setting_loop)
        self.refresh()
    def toggleDropFrames(self):
        self.setting_dropframes = not self.setting_dropframes
        if self.setting_dropframes:
            offset = self.playFrameNumber / self.fps
            self.realStartTime = time.time() - offset
            self.startAudio(offset)
        else:
            self.audio.stop()
        self.refresh()
    def toggleFpsOverride(self):
        fo = self.setting_fpsOverride
        if fo==None:
            fo = 24000.0/1001.0
        elif fo==24000.0/1001.0:
            fo = 24000.0/1000.0
        elif fo==24000.0/1000.0:
            fo = 25000.0/1000.0
        elif fo==25000.0/1000.0:
            fo = 30000.0/1001.0
        elif fo==30000.0/1001.0:
            fo = 30000.0/1000.0
        elif fo==30000.0/1000.0:
            fo = 48000.0/1000.0
        elif fo==48000.0/1000.0:
            fo = 50000.0/1000.0
        elif fo==50000.0/1000.0:
            fo = 60000.0/1000.0
        elif fo==60000.0/1000.0:
            fo = None
        self.setting_fpsOverride = fo
        if fo==None:
            self.fps = self.raw.fps
        else:
            self.fps = fo
        self.raw.setMeta("fpsOverride_v1",fo)
        self.refresh()
    def onIdle(self):
        PLOG(PLOG_FRAME,"onIdle start")
        if self.exporter.needBgDraw != self.bgActive:
            #print "changing bg draw to",self.exporter.needBgDraw
            self.setBgProcess(self.exporter.needBgDraw)
        #if self.exporter.busy:
        #    for index in self.exporter.jobs.keys():
        #        print "export",index,self.exporter.status(index)
        if self.exporter.busy:
            self.wasExporting = True
        if self.wasExporting:
            #if not self.exporter.busy:
            #    self.toggleEncoding() # Auto pause when queue finished
            newstat = 0.0
            try:
                newstat = self.exporter.jobstatus[self.exporter.currentjob]
            except:
                pass
            if (newstat < self.exportLastStatus) or ((newstat - self.exportLastStatus)>0.01):
                self.exportLastStatus = newstat
                self.refresh()
        if self.wasExporting and not self.exporter.busy:
            self.wasExporting = False

        if self.userIdleTime()>5.0 and self.userIdleTime()<7.0:
            self.refresh()

        if self.raw:
            if self.display.isDirty():
                self.refresh()

            self.handleIndexing()
            self.checkForLoadedFrames()
            wrongFrame = self.neededFrame != self.drawnFrameNumber
            if not self.needsRefresh and self.paused and not wrongFrame:
                time.sleep(0.016) # Sleep for one 60FPS frame -> Avoid burning idle function
            if not self.paused and self.raw.indexingStatus()==1.0:
                now = time.time()
                elapsed = now - self.realStartTime # Since before first frame drawn
                neededFrame = int(self.fps*elapsed)
                # Is it time for a new frame?
                newNeeded = neededFrame != self.neededFrame
                if newNeeded and not self.dropframes():
                    # In non-drop-frame mode, only step by 1 frame
                    neededFrame = self.nextFrameNumber
                if neededFrame >= self.raw.frames():
                    if self.setting_loop:
                        neededFrame = 0 #self.raw.frames() - 1 # End of file
                        self.playFrameNumber = 0
                        self.nextFrameNumber = 0
                        self.realStartTime = now
                        self.audio.stop()
                        self.startAudio()
                    else:
                        neededFrame = self.raw.frames()-1
                        self.playFrameNumber = neededFrame
                        self.nextFrameNumber = neededFrame
                        self.togglePlay() # Pause on last frame

                self.neededFrame = neededFrame
                #print "neededFrame",neededFrame,elapsed
                if newNeeded:
                    PLOG(PLOG_FRAME,"neededFrame now %d"%neededFrame)

            if self.neededFrame != self.drawnFrameNumber:
                # Yes it is
                # Do we have the needed frame available?
                if self.neededFrame in self.frameCache:
                    PLOG(PLOG_FRAME,"Using frame %d"%self.neededFrame)
                    # Yes we do. Update the frame details and queue display
                    self.playFrameNumber = self.neededFrame
                    self.nextFrameNumber = self.playFrameNumber + 1
                    self.playTime = self.neededFrame * self.fps
                    self.playFrame = self.frameCache[self.neededFrame]
                    self.needsRefresh = True
                    self.redisplay()
                else:
                    # Is there a better frame in the cache than the one we are currently displaying?
                    newer = []
                    older = []
                    for ix in self.frameCache:
                        if ix>self.neededFrame:
                            newer.append(ix)
                        if ix<self.neededFrame:
                            older.append(ix)

                    newer.sort()
                    older.sort()
                    nearest = None
                    if len(newer)>0:
                        nearest = newer[0]
                    elif len(older)>0:
                        nearest = older[-1]
                    if nearest:
                        if abs(nearest-self.neededFrame)<abs(self.neededFrame-self.playFrameNumber):
                            # It is "better"
                            # Yes we do. Update the frame details and queue display
                            self.playFrameNumber = nearest
                            self.nextFrameNumber = self.playFrameNumber + 1
                            self.playTime = nearest * self.fps
                            self.playFrame = self.frameCache[nearest]
                            self.needsRefresh = True
                            self.redisplay()
                            PLOG(PLOG_FRAME,"Using near frame %d"%nearest)
                        else:
                            time.sleep(0.003)
                    else:
                        time.sleep(0.003)
            else:
                time.sleep(0.003)

                """
                if (now-self._last >= (1.0/self.fps)):
                    self.redisplay()
                else:
                    time.sleep(0.001)
                """

        if self.needsRefresh: # and self.paused:
            self.redisplay()
            self.needsRefresh = False
        PLOG(PLOG_FRAME,"onIdle ends")

    def refresh(self):
        self.needsRefresh = True

    def checkoutfile(self,fn,ext=""):
        exists = False
        try:
            exists = os.path.exists(self.outfilename)
        except:
            pass
        if not exists:
            self.askOutputFunction() # Synchronous
            try:
                exists = os.path.exists(self.outfilename)
            except:
                pass
            if not exists:
                return None
        rfn = os.path.splitext(os.path.split(fn)[1])[0]+ext
        i = 1
        name = rfn+"_%06d"%i
        #full = os.path.join(self.outfilename,name)
        queuedfiles = [j[1][3] for j in self.exporter.jobs.items()]
        increment = True
        existing = os.listdir(self.outfilename)
        while increment:
            increment = False
            for exists in existing:
                if exists.startswith(name):
                    increment = True
                    break
            for queued in queuedfiles:
                if queued.startswith(name):
                    increment = True
                    break
            if not increment:
                break
            i += 1
            name = rfn+"_%06d"%i
        full = os.path.join(self.outfilename,name)
        return full

    def stdoutReaderLoop(self):
        try:
            buf = self.encoderProcess.stdout.readline().strip()
            while len(buf)>0:
                self.encoderOutput.append(buf)
                print "Encoder:",buf
                buf = self.encoderProcess.stdout.readline().strip()
        except:
            pass
        print "ENCODER FINISHED!"
    def toggleEncodeType(self):
        newEncodeType = (self.setting_encodeType[0]+1)%ENCODE_TYPE_MAX
        if newEncodeType == ENCODE_TYPE_MOV:
            self.setting_encodeType = (newEncodeType,) # Could be more params here
        elif newEncodeType == ENCODE_TYPE_DNG:
            self.setting_encodeType = (newEncodeType,) # Could be more params here
        config.setState("encodeType",self.setting_encodeType)
        self.refresh()
    def addEncoding(self):
        if self.setting_encodeType[0] == ENCODE_TYPE_DNG:
            self.dngExport()
        elif self.setting_encodeType[0] == ENCODE_TYPE_MOV:
            self.movExport()
    def addEncodingAll(self):
        """
        Magic button for some workflows?
        Auto-add all files in current directory using current settings
        """
        fn = self.raw.filename
        path,name = os.path.split(fn) # Correct for files and CDNG dirs
        fl = self.candidatesInDir(fn)
        c = self.setting_rgb
        rgbl = (c[0],c[1],c[2],self.setting_brightness)
        if self.setting_encodeType[0] == ENCODE_TYPE_DNG:
            for cand in fl:
                filename = os.path.join(path,cand)
                outfile = self.checkoutfile(filename,"_DNG")
                if outfile==None: return # No directory set
                wavname = os.path.splitext(filename)[0]+".WAV"
                if os.path.isdir(filename):
                    wavdir = filename
                else:
                    wavdir = os.path.split(filename)[0]
                #print filename,wavdir
                wavnames = [w for w in os.listdir(wavdir) if w.lower().endswith(".wav")]
                if os.path.isdir(filename) and len(wavnames)>0:
                    wavfilename = os.path.join(wavdir,wavnames[0])
                else:
                    wavfilename = wavname # Expect this to be extracted by indexing of MLV with SND
                #print cand,outfile,wavfilename
                pp = ExportQueue.ExportQueue.PREPROCESS_NONE
                if self.setting_preprocess:
                    pp = ExportQueue.ExportQueue.PREPROCESS_ALL
                self.exporter.exportDng(filename,outfile,wavfilename,0,None,0.0,rgbl=rgbl,preprocess=pp)

        elif self.setting_encodeType[0] == ENCODE_TYPE_MOV:
            for cand in fl:
                filename = os.path.join(path,cand)
                outfile = self.checkoutfile(filename)
                if outfile==None: return # No directory set
                wavname = os.path.splitext(filename)[0]+".WAV"
                if os.path.isdir(filename):
                    wavdir = filename
                else:
                    wavdir = os.path.split(filename)[0]
                #print filename,wavdir,wavname
                wavnames = [w for w in os.listdir(wavdir) if w.lower().endswith(".wav")]
                if os.path.isdir(filename) and len(wavnames)>0:
                    wavfilename = os.path.join(wavdir,wavnames[0])
                else:
                    wavfilename = wavname # Expect this to be extracted by indexing of MLV with SND
                #print filename,outfile,wavfilename
                pp = ExportQueue.ExportQueue.PREPROCESS_NONE
                if self.setting_preprocess:
                    pp = ExportQueue.ExportQueue.PREPROCESS_ALL
                self.exporter.exportMov(filename,outfile,wavfilename,0,None,0.0,rgbl=rgbl,tm=self.setting_tonemap,matrix=self.setting_colourMatrix,preprocess=pp)
                # Hmmm, colour matrix should be in the raw file.. shouldn't be a parameter?
        self.refresh()

    def toggleEncoding(self):
        if self.exportActive:
            self.exporter.pause()
            self.exportActive = False
        else:
            self.exporter.process()
            self.exportActive = True
        self.refresh()

    def movExport(self):
        outfile = self.checkoutfile(self.raw.filename)
        if outfile==None: return # No directory set
        c = self.setting_rgb
        rgbl = (c[0],c[1],c[2],self.setting_brightness)
        pp = ExportQueue.ExportQueue.PREPROCESS_NONE
        if self.setting_preprocess:
            pp = ExportQueue.ExportQueue.PREPROCESS_ALL
        self.exporter.exportMov(self.raw.filename,outfile,self.wavname,self.marks[0][0],self.marks[1][0],self.audioOffset,rgbl=rgbl,tm=self.setting_tonemap,matrix=self.setting_colourMatrix,preprocess=pp)
        self.refresh()

    def handleIndexing(self):
        # Do anything we need to do when indexing has completed
        if self.indexing and self.raw.indexingStatus()==1.0:
            self.indexing = False
            # Do other events here
            self.initWav() # WAV file may have been written
            self.startAudio()

    def initWav(self):
        if self.wav != None: # Already loaded
            return
        if not self.wavname:
            return
        if os.path.exists(self.wavname):
            wavname = self.wavname
            # Update the raw file metadata to point to this wav file
            self.raw.setMeta("wavfile_v1",self.wavname)
        else:
            wavname = self.raw.getMeta("wavfile_v1")
        #print "trying to load wavfile",wavname
        try:
            self.wav = wave.open(wavname,'r')
        except:
            self.wav = None
    def startAudio(self,startTime=0.0):
        if not self.setting_dropframes: return
        if not self.wav: return
        channels,width,framerate,nframe,comptype,compname = self.wav.getparams()
        self.audio.init(framerate,width,channels)
        self.wav.setpos(0)
        wavdata = self.wav.readframes(nframe)
        startTime += self.audioOffset
        start = int(startTime*framerate)*channels*width
        if start<0:
            pad = "\0"*(-start)
            wavdata = pad + wavdata
            start=0
        self.audio.play(wavdata[start:])
    def slideAudio(self,slideBy):
        self.audioOffset += slideBy
        self.raw.setMeta("audioOffset_v1",self.audioOffset)
        #if self.audioOffset <= 0.0:
        #    self.audioOffset = 0.0
        print "Audio offset = %.02f seconds"%self.audioOffset
        if not self.paused:
            now = time.time()
            offset = now - self.realStartTime
            self.startAudio(offset)

    def okToExit(self):
        if self.exporter.busy:
            result = okToExitDialog()
            return result
        else:
            return True
    def exit(self):
        self.exporter.end()
        self.audio.stop()

    # Settings interface to the scene
    def brightness(self):
        return self.setting_brightness
    def rgb(self):
        return self.setting_rgb
    def highQuality(self):
        # Only use high quality when paused if we can CPU demosaic in less than 0.5 seconds
        return self.setting_highQuality or (self.paused and self.demosaicAverage < 0.5)
    def encoding(self):
        return self.setting_encoding
    def tonemap(self):
        return self.setting_tonemap
    def dropframes(self):
        return self.setting_dropframes

    # Encoder interface to demosaicing -> frames are returned to here if encoding setting is True
    def demosaicDuration(self, duration):
        # Maintain an average measure of how long it takes this machine to CPU demosaic
        self.demosaicCount += 1
        self.demosaicTotal += duration
        self.demosaicAverage = self.demosaicTotal/float(self.demosaicCount)
        #print "demosaicAverage:",self.demosaicAverage
    def encode(self, index, frame):
        if self.setting_encoding and self.encoderProcess and self.lastEncodedFrame:
            if index < self.lastEncodedFrame or index > self.marks[1][0]:
                self.toggleEncoding() # Stop encoding as we reached the end
                self.paused = True
                self.jump(-1) # Should go back to last frame
                self.refresh()
                return
        if self.encoderProcess:
            #print "Encoding frame:",index
            self.encoderProcess.stdin.write(frame.tostring())
        self.lastEncodedFrame = index

    # Frames interface -> Manage which frame to show and the timestamp of it
    def currentFrame(self):
        return self.playFrame # Always available
    def currentFrameNumber(self):
        return self.playFrameNumber
    def currentTime(self):
        return self.playTime

    # Manage the frame progression
    def preloadFrame(self,index):
        if index in self.frameCache:
            return # Already available in the cache
        if index in self.preloadingFrame:
            return # Currently being loaded
        if index in self.preloadingFrames:
            return # Currently in queue to be loaded
        else:
            self.preloadingFrames.append(index)
        self.preloadingFrames.sort()
        if len(self.preloadingFrames)>10:
            self.preloadingFrames = self.preloadingFrames[-10:]
        nextindex = self.preloadingFrames.pop() # Last in list
        while nextindex in self.frameCache:
            if len(self.preloadingFrames)==0:
                return
            nextindex = self.preloadingFrames.pop() # Last in list
        if len(self.preloadingFrame) == 2:
            return # Don't preload more than 2 frames
        self.preloadingFrame.append(nextindex)
        #print "preloading",index
        PLOG(PLOG_FRAME,"Calling preload for frame %d"%nextindex)
        self.raw.preloadFrame(nextindex)
        PLOG(PLOG_FRAME,"Returned from preload for frame %d"%nextindex)
    def manageFrameCache(self):
        if len(self.frameCache)>10: # Cache 10 frames at most
            # Don't remove currently showing frame
            indexes = [k for k in self.frameCache.keys() if k != self.playFrameNumber]
            indexes.sort()
            #print indexes
            if indexes[0] < self.neededFrame:
                # Remove the one furthest behind the current frame number
                PLOG(PLOG_FRAME,"Calling head %d from frame cache"%indexes[0])
                del self.frameCache[indexes[0]]
            else: # Otherwise delete the last one
                PLOG(PLOG_FRAME,"Calling tip %d from frame cache"%indexes[-1])
                del self.frameCache[indexes[-1]]
    def manageFrameLoading(self):
        if self.neededFrame != None:
            #print "looking for neededFrame",self.neededFrame
            # Try to ensure we have a few frames ahead of the currently needed frame
            # First preload +1,+1,+0
            if self.paused or not self.dropframes():
                for n in range(self.neededFrame,self.neededFrame+3):
                    if n>=self.raw.frames():
                        n -= self.raw.frames() # Start preloading from beginning
                    if n not in self.frameCache:
                        self.preloadFrame(n)
            else:
                for n in range(self.neededFrame+5,self.neededFrame-1,-1):
                    if n>=self.raw.frames():
                        n -= self.raw.frames() # Start preloading from beginning
                    if n not in self.frameCache:
                        self.preloadFrame(n)

    def checkForLoadedFrames(self):
        if len(self.preloadingFrame) > 0:
            if self.raw.isPreloadedFrameAvailable():
                frameIndex,preloadedFrame = self.raw.nextFrame()
                self.preloadingFrame.remove(frameIndex)
                PLOG(PLOG_FRAME,"Received preloaded frame %d"%frameIndex)
                # Add it to the cache
                self.frameCache[frameIndex] = preloadedFrame
                self.manageFrameCache()
        self.manageFrameLoading()
    MARK_IN = 0
    MARK_OUT = 1
    def markLoad(self):
        self.marks = self.raw.getMeta("marks_v1")
        if self.marks == None:
            self.markReset() # Set valid marks
    def markSet(self,newmarks):
        if newmarks == self.marks:
            return
        self.marks = newmarks
        self.raw.setMeta("marks_v1",newmarks)
    def markReset(self):
        # By default, start at start and end at end, whole file in scope
        self.markSet([(0,self.MARK_IN),(self.raw.frames()-1,self.MARK_OUT)])
        #Aprint "markReset",self.marks
    def markNext(self):
        #print "markNext"
        this = self.playFrameNumber
        for frame,mt in self.marks:
            if this < frame:
                self.jumpTo(frame)
                break
    def markPrev(self):
        #print "markPrev"
        this = self.playFrameNumber
        lastframe = None
        for frame,mt in self.marks:
            if this <= frame:
                if lastframe != None:
                    self.jumpTo(lastframe)
                return
            lastframe = frame
        self.jumpTo(lastframe)
    def markIn(self):
        #print "markIn",self.playFrameNumber
        self.markAt(self.playFrameNumber,self.MARK_IN)
    def markOut(self):
        #print "markOut",self.playFrameNumber
        self.markAt(self.playFrameNumber,self.MARK_OUT)
    def markAt(self,at,markType):
        """
        Implement the mark management logic
        For now we only allow one pair
        Start/End are implicitly used when needed to create a pair
        """
        marks = list(self.marks)
        index = 0
        insert = True
        mark = (at,markType)
        # Find index
        for frame,kind in marks:
            if frame==at:
                insert = False
                break
            elif frame>at:
                break
            index += 1
        # Do the correct operation
        if insert:
            if index==len(marks):
                # Adding a new mark at the end
                if kind == markType:
                    #print "replacing prev mark",index
                    marks[index-1] = mark
                else:
                    marks[index-2] = mark
                    marks[index-1] = (self.raw.frames()-1,self.MARK_OUT)
                """
                    if markType==self.MARK_IN: # Must add end as out
                        self.marks.append((self.raw.frames(),self.MARK_OUT)
                elsAe:
                """
            elif index==0:
                # Adding a new mark at the start
                if kind == markType:
                    #print "replacing next mark",index
                    marks[index] = mark
                else:
                    marks[index] = (0,self.MARK_IN)
                    marks[index+1] = mark
            elif markType == kind:
                # We are inserting same kind of mark as the one after -> replace that
                #print "replacing next mark",index
                marks[index] = mark
            else:
                # We are inserting same kind of mark as the previous one -> replace that
                #print "replacing prev mark",index
                marks[index-1] = mark
        else:
            pass
            #if kind != markType:
            #    print "deleting mark",index
            #    del self.marks[index]

        self.markSet(marks)
        #print self.marks
        self.refresh()

    def dngExport(self):
        outfile = self.checkoutfile(self.raw.filename,"_DNG")
        if outfile==None: return # No directory set
        c = self.setting_rgb
        rgbl = (c[0],c[1],c[2],self.setting_brightness)
        pp = ExportQueue.ExportQueue.PREPROCESS_NONE
        if self.setting_preprocess:
            pp = ExportQueue.ExportQueue.PREPROCESS_ALL
        self.exporter.exportDng(self.raw.filename,outfile,self.wavname,self.marks[0][0],self.marks[1][0],self.audioOffset,rgbl=rgbl,preprocess=pp)
        self.refresh()

    def askOutput(self):
        """
        Temporary way to set output target
        """
        askThread = threading.Thread(target=self.askOutputFunction)
        askThread.daemon = True
        askThread.start()

    def askOutputFunction(self):
        result = askOutputDialog(self.outfilename)
        if not result:
            return
        if os.path.exists(result):
            self.outfilename = result
            config.setState("targetDir",result)

    def useWhitePoint(self,x,y):
        # Read from the current playFrame at x/y
        # Assume that is a neutral colour
        # Set the white balance accordingly
        haveColour = False
        if self.playFrame.rawimage != None:
            f = self.playFrame.rawimage
            bl = self.playFrame.black
            f2 = f.reshape(self.raw.height(),self.raw.width())
            bx = int(x/2)*2
            by = int(y/2)*2
            red = f2[by,bx]-bl
            green = (f2[by,bx+1]+f2[by+1,bx]-bl*2)/2
            blue = f2[by+1,bx+1]-bl
            haveColour = True
        elif self.playFrame.rgbimage != None:
            f = self.playFrame.rgbimage
            bl = self.playFrame.black
            bufsize = self.raw.height()*self.raw.width()*3
            f2 = f[:bufsize].reshape(self.raw.height(),self.raw.width(),3)
            bx = int(x)
            by = int(y)
            red = f2[by,bx,0]
            green = (f2[by,bx,1]+f2[by,bx,1])/2
            blue = f2[by,bx,2]
            haveColour = True
        if haveColour:
            red = red/self.playFrame.rawwbal[0]
            blue = blue/self.playFrame.rawwbal[2]
            redMul = float(green)/float(red)
            blueMul = float(green)/float(blue)
            #self.setting_rgb = (redMul,1.0,blueMul)
            self.changeWhiteBalance(redMul,1.0,blueMul,"User")
            #print "Setting white Balance from",x,y,"to",self.setting_rgb,self.playFrame.rawwbal
            #self.refresh()

    def updateColourMatrix(self):
        # First do the white balance
        if self.raw.whiteBalance != None:
            self.setting_rgb = self.raw.whiteBalance
        newbalance = self.raw.getMeta("balance_v1")
        if newbalance != None: self.setting_rgb = newbalance
        #else:
        #    self.setting_rgb = (2.0, 1.0, 1.5)
        self.setting_brightness = self.raw.brightness
        newbrightness = self.raw.getMeta("brightness_v1")
        if newbrightness != None: self.setting_brightness = newbrightness

        newtm = self.raw.getMeta("tonemap_v1")
        if newtm != None: self.setting_tonemap = newtm

        # This calculation should give results matching dcraw
        camToXYZ = self.raw.colorMatrix
        # D50
        #XYZtosRGB = np.matrix([[3.1338561, -1.6168667, -0.4906146],
        #                        [-0.9787684,  1.9161415,  0.0334540],
        #                        [ 0.0719453, -0.2289914,  1.4052427]])
        # D65
        XYZtosRGB = np.matrix([[3.2404542,-1.5371385,-0.4985314],
                                [-0.9692660,1.8760108,0.0415560],
                                [0.0556434,-0.2040259,1.0572252]])
        rgb2cam = camToXYZ * XYZtosRGB.getI()
        # Normalise the matrix
        rgb2cam[0,:]/=np.sum(rgb2cam[0])
        rgb2cam[1,:]/=np.sum(rgb2cam[1])
        rgb2cam[2,:]/=np.sum(rgb2cam[2])
        cam2rgb = rgb2cam.getI()
        self.setting_colourMatrix = cam2rgb.getT() # Must be transposed
        self.setting_lut3d = self.raw.getMeta("lut3d_v1")
        if type(self.setting_lut3d)==tuple:
            self.setting_lut3d = None
        if self.setting_lut3d != None:
            if self.setting_lut3d.len()==0 or len(self.setting_lut3d.lut())==0:
                self.setting_lut3d = None
        self.setting_lut1d1 = self.raw.getMeta("lut1d1_v1")
        if self.setting_lut1d1 != None:
            if self.setting_lut1d1.len()==0 or len(self.setting_lut1d1.lut())==0:
                self.setting_lut1d1 = None
        self.setting_lut1d2 = self.raw.getMeta("lut1d2_v1")
        if self.setting_lut1d2 != None:
            if self.setting_lut1d2.len()==0 or len(self.setting_lut1d2.lut())==0:
                self.setting_lut1d2 = None
    def onBgDraw(self,w,h):
        self.exporter.onBgDraw(w,h)

    def saveBalance(self):
        """
        Save current colour balance and brightness
        globally for matching takes
        """
        config.setState("balance",(self.setting_rgb,self.setting_brightness))

    def loadBalance(self):
        """
        Load saved colour balance and brightness
        """
        rgbl = config.getState("balance")
        if rgbl != None:
            rgb,l = rgbl
            r,g,b = rgb
            self.changeWhiteBalance(r,g,b,"Shared")
            self.setBrightness(l)
            self.refresh()

    def toggleBrowser(self):
        if not self.browser:
            if not self.paused:
                self.togglePlay()
            self.dialog.browse(*os.path.split(self.raw.filename))
            self.dialog.hidden = False
            self.display.hidden = True
            self.demosaic.hidden = True
            self.browser = True
            self.setCursorVisible(True)
        else:
            if not self.raw:
                self.close()
            else:
                self.dialog.hidden = True
                self.display.hidden = False
                self.demosaic.hidden = False
            self.outfilename = config.getState("targetDir") # In case it changed
            self.browser = False
        self.refresh()

    def toggleChooseExport(self):
        if not self.browser:
            if not self.paused:
                self.togglePlay()
            self.dialog.chooseExport()
            self.dialog.hidden = False
            self.display.hidden = True
            self.demosaic.hidden = True
            self.browser = True
            self.setCursorVisible(True)
        else:
            self.dialog.hidden = True
            self.display.hidden = False
            self.demosaic.hidden = False
            self.browser = False
        self.refresh()

def launchDialog(dialogtype,initial="None"):
    import codecs
    toUtf8=codecs.getencoder('UTF8')
    fromUtf8=codecs.getdecoder('UTF8')
    initialUtf8 = toUtf8(initial)[0]
    kwargs = {"stdout":subprocess.PIPE}
    frozen = getattr(sys,'frozen',False)
    if config.isMac() and frozen:
        exepath = os.path.join(sys._MEIPASS,"dialogs")
        args = [exepath,dialogtype,initialUtf8]
    elif config.isWin() and frozen:
        kwargs = {"stdin":subprocess.PIPE,"stdout":subprocess.PIPE,"stderr":subprocess.STDOUT}
        if subprocess.mswindows:
            su = subprocess.STARTUPINFO()
            su.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            su.wShowWindow = subprocess.SW_HIDE
            kwargs["startupinfo"] = su
        exepath = os.path.join(sys._MEIPASS,"dialogs.exe")
        args = [exepath,dialogtype,initialUtf8]
    else:
        args = ["python","dialogs.py",dialogtype,initialUtf8]
    #print "args:",args
    #print "kwargs:",kwargs
    p = subprocess.Popen(args,**kwargs)
    #print p
    result = fromUtf8(p.stdout.read())[0].strip()
    #print "result",result
    p.wait()
    return result

def okToExitDialog():
    result = launchDialog("okToExit")
    if result=="True":
        return True
    else:
        return False

def askOutputDialog(initial):
    result = launchDialog("chooseOutputDir",initial)
    return result
