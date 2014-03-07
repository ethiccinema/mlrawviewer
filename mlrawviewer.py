#!/usr/bin/python2.7
"""
mlrawviewer.py
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

# standard python imports. Should not be missing
import sys,struct,os,math,time,datetime,subprocess,signal,threading,Queue,wave,zlib
from threading import Thread

from Config import Config

config = Config(version=(1,1,0))

programpath = os.path.abspath(os.path.split(sys.argv[0])[0])
if getattr(sys,'frozen',False):
    programpath = sys._MEIPASS
    # Assume we have no console, so try to redirect output to a log file...somewhere
    try:
        sys.stdout = file("mlrawviewer.log","a")
        sys.stderr = sys.stdout
    except:
        pass

print "MlRawViewer v"+config.versionString()
print "(c) Andrew Baldwin & contributors 2013-2014"

noAudio = True
try:
    import pyaudio
    noAudio = False
except Exception,err:
    print "pyAudio not available. Cannot play audio"

# OpenGL. Could be missing
try:
    import OpenGL
    #OpenGL.ERROR_CHECKING = False # Only for one erroneously-failing Framebuffer2DEXT call on Windows with Intel...grrr
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
import PerformanceLog
from PerformanceLog import PLOG
PerformanceLog.PLOG_CONTROL(False)
PLOG_FILE_IO = PerformanceLog.PLOG_TYPE(0,"FILE_IO")
PLOG_FRAME = PerformanceLog.PLOG_TYPE(1,"FRAME")
PLOG_CPU = PerformanceLog.PLOG_TYPE(2,"CPU")
PLOG_GPU = PerformanceLog.PLOG_TYPE(3,"GPU")

import GLCompute
import GLComputeUI as ui
import MlRaw
from Matrix import *
from ShaderDemosaicNearest import *
from ShaderDemosaicBilinear import *
from ShaderDemosaicCPU import *
from ShaderDisplaySimple import *
from ShaderText import *

class Demosaicer(ui.Drawable):
    def __init__(self,settings,encoder,frames,**kwds):
        super(Demosaicer,self).__init__(**kwds)
        self.shaderNormal = ShaderDemosaicBilinear()
        self.shaderQuality = ShaderDemosaicCPU()
        self.settings = settings
        self.encoder = encoder
        self.lastFrameData = None
        self.lastFrameNumber = None
        self.lastBrightness = None
        self.lastRgb = None
        self.lastTone = None
        self.frames = frames # Frame fetching interface
        self.rgbFrameUploaded = None

    def setTextures(self,rawUploadTex,rgbUploadTex):
        self.rawUploadTex = rawUploadTex
        self.rgbUploadTex = rgbUploadTex

    def render(self,scene,matrix):
        frameData = self.frames.currentFrame()
        frameNumber = self.frames.currentFrameNumber()

        brightness = self.settings.brightness()
        rgb = self.settings.rgb()
        balance = (rgb[0]*brightness, rgb[1]*brightness, rgb[2]*brightness)
        tone = self.settings.tonemap()
        different = (frameData != self.lastFrameData) or (brightness != self.lastBrightness) or (rgb != self.lastRgb) or (frameNumber != self.lastFrameNumber) or (tone != self.lastTone)
        if (frameData and different):
            if ((frameData.rgbimage!=None) or self.settings.highQuality() or self.settings.encoding()) and (frameData.canDemosaic):
                # Already rgb available, or else low/high quality decode for static view or encoding
                PLOG(PLOG_CPU,"CPU Demosaic started for frame %d"%frameNumber)
                before = time.time()
                frameData.demosaic()
                PLOG(PLOG_CPU,"CPU Demosaic completed for frame %d"%frameNumber)
                after = time.time()
                self.encoder.demosaicDuration(after-before)
                if (frameData != self.lastFrameData) or (self.rgbFrameUploaded != frameNumber):
                    PLOG(PLOG_GPU,"RGB texture upload called for frame %d"%frameNumber)
                    self.rgbUploadTex.update(frameData.rgbimage)
                    PLOG(PLOG_GPU,"RGB texture upload returned for frame %d"%frameNumber)
                    self.rgbFrameUploaded = frameNumber
                self.shaderQuality.demosaicPass(self.rgbUploadTex,frameData.black,balance=balance,white=frameData.white,tonemap=tone)
                if self.settings.encoding():
                    self.rgb = glReadPixels(0,0,scene.size[0],scene.size[1],GL_RGB,GL_UNSIGNED_SHORT)
                    self.encoder.encode(frameNumber,self.rgb)

            else:
                # Fast decode for full speed viewing
                if frameData != self.lastFrameData:
                    PLOG(PLOG_CPU,"Bayer 14-16 convert starts for frame %d"%frameNumber)
                    frameData.convert()
                    PLOG(PLOG_CPU,"Bayer 14-16 convert done for frame %d"%frameNumber)
                    self.rawUploadTex.update(frameData.rawimage)
                PLOG(PLOG_GPU,"Demosaic shader draw for frame %d"%frameNumber)
                self.shaderNormal.demosaicPass(self.rawUploadTex,frameData.black,balance=balance,white=frameData.white,tonemap=self.settings.tonemap())
                PLOG(PLOG_GPU,"Demosaic shader draw done for frame %d"%frameNumber)
        self.lastFrameData = frameData
        self.lastFrameNumber = frameNumber
        self.lastBrightness = brightness
        self.lastRgb = rgb
        self.lastTone = tone

class DemosaicScene(ui.Scene):
    def __init__(self,raw,settings,encoder,frames,**kwds):
        super(DemosaicScene,self).__init__(**kwds)
        self.frames = frames
        self.demosaicer = Demosaicer(settings,encoder,frames)
        self.initTextures()
        self.drawables.append(self.demosaicer)
        #print "Width:",self.raw.width(),"Height:",self.raw.height(),"Frames:",self.raw.frames()
    def initTextures(self):
        raw = self.frames.raw
        self.rawUploadTex = GLCompute.Texture((raw.width(),raw.height()),None,hasalpha=False,mono=True,sixteen=True)
        #try: self.rgbUploadTex = GLCompute.Texture((self.raw.width(),self.raw.height()),None,hasalpha=False,mono=False,fp=True)
        self.rgbUploadTex = GLCompute.Texture((raw.width(),raw.height()),None,hasalpha=False,mono=False,sixteen=True)
        try: self.rgbImage = GLCompute.Texture((raw.width(),raw.height()),None,hasalpha=False,mono=False,fp=True)
        except GLError: self.rgbImage = GLCompute.Texture((raw.width(),raw.height()),None,hasalpha=False,sixteen=True)
        self.demosaicer.setTextures(self.rawUploadTex,self.rgbUploadTex)
        #print "Using",self.demosaicer.shaderNormal.demosaic_type,"demosaic algorithm"
    def setTarget(self):
        self.rgbImage.bindfbo()
    def free(self):
        self.rawUploadTex.free()
        self.rgbUploadTex.free()
        self.rgbImage.free()
    def prepareToRender(self):
        self.demosaicer.shaderNormal.prepare(self.frames.svbo)
        self.demosaicer.shaderQuality.prepare(self.frames.svbo)

class Display(ui.Drawable):
    def __init__(self,**kwds):
        super(Display,self).__init__(**kwds)
        self.displayShader = ShaderDisplaySimple()
    def setRgbImage(self,rgbImage):
        self.rgbImage = rgbImage
    def render(self,scene,matrix):
        # Now display the RGB image
        #self.rgbImage.addmipmap()
        # Balance now happens in demosaicing shader
        balance = (1.0,1.0,1.0)
        # Scale
        PLOG(PLOG_GPU,"Display shader draw")
        self.displayShader.draw(scene.size[0],scene.size[1],self.rgbImage,balance)
        PLOG(PLOG_GPU,"Display shader draw done")
        # 1 to 1
        # self.displayShader.draw(self.rgbImage.width,self.rgbImage.height,self.rgbImage,balance)

class DisplayScene(ui.Scene):
    def __init__(self,frames,**kwds):
        super(DisplayScene,self).__init__(**kwds)
        self.frames = frames # Frames interface
        self.icons = zlib.decompress(file(os.path.join(programpath,"data/icons.z"),'rb').read())
        self.iconsz = int(math.sqrt(len(self.icons)))
        self.icontex = GLCompute.Texture((self.iconsz,self.iconsz),rgbadata=self.icons,hasalpha=False,mono=True,sixteen=False,mipmap=True)
        self.display = Display()
        self.iconBackground = ui.Geometry(svbo=frames.svbo)
        self.iconBackground.edges = (1.0,1.0,0.35,0.25)
        self.mark = ui.Geometry(svbo=frames.svbo)
        self.mark.edges = (1.0,1.0,0.01,0.6)
        self.progressBackground = ui.Geometry(svbo=frames.svbo)
        self.progressBackground.edges = (1.0,1.0,0.01,0.25)
        self.progress = ui.Button(0,0,self.progressClick,svbo=frames.svbo)
        self.progress.edges = (1.0,1.0,0.01,0.5)
        self.play = self.newIcon(0,0,128,128,0,self.playClick)
        self.play.colour = (0.5,0.5,0.5,0.5) # Quite transparent white
        self.quality = self.newIcon(0,0,128,128,5,self.qualityClick)
        self.quality.colour = (0.5,0.5,0.5,0.5) # Quite transparent white
        self.quality.setScale(0.25)
        self.drop = self.newIcon(0,30,128,128,7,self.dropClick)
        self.drop.colour = (0.5,0.5,0.5,0.5) # Quite transparent white
        self.drop.setScale(0.25)
        self.fullscreen = self.newIcon(0,60,128,128,9,self.fullscreenClick)
        self.fullscreen.colour = (0.5,0.5,0.5,0.5) # Quite transparent white
        self.fullscreen.setScale(0.25)
        self.mapping = self.newIcon(0,90,128,128,11,self.mappingClick)
        self.mapping.colour = (0.5,0.5,0.5,0.5) # Quite transparent white
        self.mapping.setScale(0.25)
        self.update = self.newIcon(0,0,128,128,14,self.updateClick)
        self.update.colour = (0.5,0.1,0.0,0.5)
        self.update.setScale(0.5)
        self.loop = self.newIcon(0,0,128,128,15,self.loopClick)
        self.loop.colour = (0.5,0.5,0.5,0.5)
        self.loop.setScale(0.5)
        self.encode = self.newIcon(0,0,128,128,2,self.encodeClick)
        self.encode.colour = (0.2,0.0,0.0,0.5)
        self.encode.setScale(0.5)
        self.balance = ui.XYGraph(128,128,self.balanceClick,svbo=self.frames.svbo)
        self.balance.gradient(128,128,tl=(0.25,0.0,0.0,0.25),tr=(0.25,0.0,0.25,0.25),bl=(0.0,0.0,0.0,0.25),br=(0.0,0.0,0.25,0.25))
        self.balance.edges = (1.0,1.0,0.05,0.05)
        self.balanceHandle = self.newIcon(0,0,8,8,2,None)
        self.balanceHandle.colour = (0.5,0.5,0.5,0.5)
        self.balanceHandle.ignoreInput = True
        self.brightness = ui.XYGraph(32,128,self.brightnessClick,svbo=self.frames.svbo)
        self.brightness.gradient(32,128,tl=(0.25,0.25,0.25,0.25),tr=(0.25,0.25,0.25,0.25),bl=(0.0,0.0,0.0,0.25),br=(0.0,0.0,0.0,0.25))
        self.brightness.edges = (1.0,1.0,0.2,0.05)
        self.brightnessHandle = self.newIcon(0,0,8,8,2,None)
        self.brightnessHandle.colour = (0.5,0.5,0.5,0.5)
        self.brightnessHandle.ignoreInput = True
        self.timestamp = ui.Geometry(svbo=frames.svbo)
        self.iconItems = [self.fullscreen,self.mapping,self.drop,self.quality,self.loop,self.encode,self.play]
        self.overlay = [self.iconBackground,self.progressBackground,self.progress,self.timestamp,self.update,self.balance,self.balanceHandle,self.brightness,self.brightnessHandle,self.mark]
        self.overlay.extend(self.iconItems)
        self.drawables.extend([self.display])
        self.drawables.extend(self.overlay)
        self.timeline = ui.Timeline()
        self.fadeAnimation = ui.Animation(self.timeline,1.0)

    def setRgbImage(self,rgbImage):
        self.display.setRgbImage(rgbImage)

    def progressClick(self,x,y):
        targetFrame = self.frames.raw.frames()*(float(x)/float(self.progress.size[0]))
        #print "Progress click",x,y,"targetFrame",targetFrame
        self.frames.jumpTo(targetFrame)
    
    def updateClick(self,x,y):
        global config
        import webbrowser
        webbrowser.open("https://bitbucket.org/baldand/mlrawviewer/downloads")
        config.updateClickedNow()

    def balanceClick(self,x,y):
        r = 4.0*(1.0-y/128.0)
        b = 4.0*(x/128.0)
        g = 1.0
        self.frames.changeWhiteBalance(r,g,b,"%f,%f,%f"%(r,g,b))
        if self.frames.paused:
            self.frames.refresh()

    def brightnessClick(self,x,y):
        b = 15.0*(1.0-y/128.0)-5.0
        b2 = math.pow(2.0,b)
        self.frames.setting_brightness = b2
        #self.frames.changeWhiteBalance(r,g,b,"%f,%f,%f"%(r,g,b))
        if self.frames.paused:
            self.frames.refresh()

    def playClick(self,x,y):
        self.frames.togglePlay()

    def loopClick(self,x,y):
        self.frames.toggleLooping()

    def mappingClick(self,x,y):
        self.frames.toggleToneMapping()

    def fullscreenClick(self,x,y):
        self.frames.toggleFullscreen()

    def qualityClick(self,x,y):
        self.frames.toggleQuality()
    
    def dropClick(self,x,y):
        self.frames.toggleDropFrames()

    def encodeClick(self,x,y):
        self.frames.toggleEncoding()

    def newIcon(self,x,y,w,h,idx,cb):
        icon = ui.Button(w,h,cb,svbo=self.frames.svbo)
        self.setIcon(icon,w,h,idx)
        icon.setPos(x,y)
        icon.colour = (1.0,1.0,1.0,1.0)
        icon.idx = idx
        #icon.setTransformOffset(64.0,64.0)
        return icon

    def setIcon(self,icon,w,h,idx):
        ix = idx%(self.iconsz/128)
        iy = idx/(self.iconsz/128)
        s = 128.0/float(self.iconsz)
        icon.rectangle(w,h,uv=(ix*s,iy*s,s,s),solid=0.0,tex=0.0,tint=0.0,texture=self.icontex)

    def updateIcons(self):
        # Make sure we show correct icon for current state
        # Model is to show icon representing CURRENT state
        f = self.frames
        states = [not f._isFull,f.tonemap(),not f.dropframes(),f.setting_highQuality,not f.setting_loop,False,f.paused]
        for i in range(len(self.iconItems)):
            itm = self.iconItems[i]
            state = states[i]
            if state!=int(state):
                if state: state = 1
                else: state = 0
            self.setIcon(itm,128,128,itm.idx+state)
        if self.frames.encoding():
            self.encode.colour = (0.5,0.0,0.0,0.5)
        else:
            self.encode.colour = (0.2,0.0,0.0,0.5)

    def prepareToRender(self):
        """
        f = self.frame
        frameNumber = int(f % self.raw.frames())
        """
        self.display.displayShader.prepare(self.frames.svbo)
        self.timeline.setNow(time.time())
        idle = self.frames.userIdleTime()
        if idle>5.0 and self.fadeAnimation.targval == 1.0 and not self.frames.encoding():
            self.fadeAnimation.setTarget(0.0,2.0,0.0,ui.Animation.SMOOTH)
            
            self.frames.setCursorVisible(False)
        elif idle<=5.0 and self.fadeAnimation.targval == 0.0:
            self.fadeAnimation.setTarget(1.0,0.5,0.0,ui.Animation.SMOOTH)
            self.frames.setCursorVisible(True)
        self.overlayOpacity = self.fadeAnimation.value()
        if self.frames.paused: self.overlayOpacity = 1.0
        frameNumber = self.frames.currentFrameNumber()
        frameTime = self.frames.currentTime()
        width,height = self.size
        rectWidth = width - 70.0
        rectHeight = 30
        self.update.setPos(width-64-10,10)
        self.iconBackground.setPos(-20.0,40.0)
        self.iconBackground.rectangle(80,height,rgba=(0.0,0.0,0.0,0.25))
        iconSpacing = 40.0
        base = height - len(self.iconItems)*iconSpacing
        for i in self.iconItems:
            i.setScale(0.25)
            i.setPos(10.0,base)
            base += iconSpacing
        markstart = float(self.frames.marks[0][0])/float(self.frames.raw.frames())
        marklen = float(self.frames.marks[1][0] - self.frames.marks[0][0] + 1)/float(self.frames.raw.frames())
        self.mark.setPos(60.0+rectWidth*markstart,height-6.0)
        self.mark.rectangle(rectWidth*marklen,3.0,rgba=(0.75,0.75,0.75,0.75))
        self.progressBackground.setPos(60.0,height-rectHeight-7.0)
        self.progressBackground.rectangle(rectWidth*self.frames.raw.indexingStatus(),rectHeight,rgba=(1.0-0.8*self.frames.raw.indexingStatus(),0.2,0.2,0.2))
        self.progress.setPos(60.0,height-rectHeight-7.0)
        btl,btr = (width-128.0-10.0,height-rectHeight-10.0-128.0-5.0)
        self.balance.setPos(btl,btr)
        rgb = self.frames.rgb()
        r = ((4.0-rgb[0])/4.0)*128.0
        b = (rgb[2]/4.0)*128.0
        self.balanceHandle.setPos(btl+b-4.0,btr+r-4.0)
        rtl,rtr = (width-128.0-10.0-32.0-10.0,height-rectHeight-10.0-128.0-5.0)
        self.brightness.setPos(rtl,rtr)
        b = math.log(self.frames.setting_brightness,2.0)
        b2 = 128.0-128.0*((b+5.0)/15.0)
        self.brightnessHandle.setPos(rtl+16.0-4.0,rtr+b2-4.0)
        self.updateIcons() 
        progWidth = (float(frameNumber)/float(self.frames.raw.frames()-1))*rectWidth
        self.progress.size = (rectWidth,rectHeight) # For input checking
        self.progress.rectangle(progWidth,rectHeight,rgba=(0.2,0.2,0.01,0.2))
        self.timestamp.setPos(66.0,height-rectHeight-1.0)
        self.timestamp.setScale(9.0/30.0)
        totsec = float(frameNumber)/self.frames.raw.fps
        minutes = int(totsec/60.0)
        seconds = int(totsec%60.0)
        fsec = (totsec - int(totsec))*1000.0
        # NOTE: We use one-based numbering for the frame number display because it is more natural -> ends on last frame
        if self.frames.raw.indexingStatus()==1.0:
            self.timestamp.label("%02d:%02d.%03d (%d/%d)"%(minutes,seconds,fsec,frameNumber+1,self.frames.raw.frames()))
        else:
            self.timestamp.label("%02d:%02d.%03d (%d/%d) Indexing %s: %d%%"%(minutes,seconds,fsec,frameNumber+1,self.frames.raw.frames(),self.frames.raw.description(),self.frames.raw.indexingStatus()*100.0))
        self.timestamp.colour = (0.0,0.0,0.0,1.0)
        ua = config.isUpdateAvailable()
        uc = config.versionUpdateClicked()
        showUpdate = ua and (ua != uc)
        for o in self.overlay:
            o.opacity = self.overlayOpacity
        if showUpdate:
            self.update.opacity = self.overlayOpacity
            self.update.ignoreInput = False
        else:
            self.update.opacity = 0.0
            self.update.ignoreInput = True

class Audio(object):
    INIT = 0
    PLAY = 1
    STOP = 2
    def __init__(self):
        global noAudio
        self.playThread = threading.Thread(target=self.audioLoop)
        self.playThread.daemon = True
        self.commands = Queue.Queue(1)
        if not noAudio:
            self.playThread.start()
    def init(self,sampleRate,sampleWidth,channels):
        global noAudio
        if not noAudio:
            self.commands.put((Audio.INIT,(sampleRate,sampleWidth,channels)))
    def play(self,data):
        global noAudio
        if not noAudio:
            self.commands.put((Audio.PLAY,data))
    def stop(self):
        global noAudio
        if not noAudio:
            self.commands.put((Audio.STOP,None))
    def audioLoop(self):
        pa = pyaudio.PyAudio()
        dataBuffer = None
        bufferOffset = 0
        frameSize = 0
        stream = None
        while 1:
            if self.commands.empty() and dataBuffer != None and stream != None:
                bufSize = 1024 * frameSize
                left = len(dataBuffer)-bufferOffset
                if left<bufSize:
                    stream.write(dataBuffer[bufferOffset:])
                    dataBuffer = None
                else:
                    newoffset = bufferOffset+bufSize
                    stream.write(dataBuffer[bufferOffset:newoffset])
                    bufferOffset = newoffset
            else:
                command = self.commands.get()
                commandType,commandData = command
                if commandType==Audio.INIT:
                    # print "Init",commandData
                    if stream == None:
                        try:
                            sampleRate,sampleWidth,chn = commandData
                            fmt = pa.get_format_from_width(sampleWidth)
                            stream = pa.open(format=fmt,channels=chn,rate=sampleRate,output=True,start=False)
                            frameSize = sampleWidth * chn
                        except:
                            import traceback
                            traceback.print_exc()
                            stream = None
                    if stream != None:
                        stream.start_stream()
                if commandType==Audio.PLAY:
                    # print "Play",len(commandData)
                    dataBuffer = commandData
                    bufferOffset = 0
                elif commandType==Audio.STOP:
                    # print "Stop"
                    if stream != None:
                        stream.stop_stream()
                        dataBuffer = None

class Viewer(GLCompute.GLCompute):
    def __init__(self,raw,outfilename,wavfilename=None,**kwds):
        userWidth = 720
        self.vidAspectHeight = float(raw.height())/(raw.width()) # multiply this number on width to give height in aspect
        self.vidAspectWidth = float(raw.width())/(raw.height()) # multiply this number on height to give height in aspect
        self.raw = raw
        super(Viewer,self).__init__(width=userWidth,height=int(userWidth*self.vidAspectHeight),**kwds)
        self._init = False
        self.display = None
        self.realStartTime = 0
        self.playTime = 0
        self.playFrameNumber = 0
        self.nextFrameNumber = 0
        self.neededFrame = 0
        self.drawnFrameNumber = None
        self.playFrame = self.raw.firstFrame
        self.frameCache = {0:self.raw.firstFrame}
        self.preloadingFrame = 0
        self.preloadingFrames = []
        self.preloadFrame(1) # Immediately try to preload the next frame
        self.fps = raw.fps
        self.paused = False
        self.needsRefresh = False
        self.anamorphic = False
        self.encoderProcess = None
        self.outfilename = outfilename
        self.lastEncodedFrame = None
        self.demosaicCount = 0
        self.demosaicTotal = 0.0
        self.demosaicAverage = 0.0
        self.audio = Audio()
        self.wavname = wavfilename
        self.wav = None
        self.indexing = True
        self.audioOffset = 0.0
        self.lastEventTime = time.time()
        self.wasFull = False
        self.demosaic = None
        self.markReset()
        # Shared settings
        self.setting_brightness = 16.0
        self.setting_rgb = (2.0, 1.0, 1.5)
        self.setting_highQuality = False
        self.setting_encoding = False
        self.setting_tonemap = 1 # Global tone map, 2 = Log
        self.setting_dropframes = True # Real time playback by default
        self.setting_loop = config.getState("loopPlayback")
        if self.setting_loop == None: self.setting_loop = True
        self.svbo = None
        self.fpsMeasure = None
        self.fpsCount = 0

    def loadNewRawSet(self,step):
        fn = self.raw.filename
        path,name = os.path.split(fn) # Correct for files and CDNG dirs
        fl = [f for f in os.listdir(path) if f.lower().endswith(".mlv") or f.lower().endswith(".raw")]
        fl.sort()
        current = fl.index(name)
        newOne = (current + step)%len(fl)
        found = False
        while not found:
            newname = os.path.join(path,fl[newOne])
            print "Loading",newname
            try:
                r = MlRaw.loadRAWorMLV(newname)
                found = True
            except:
                pass
            newOne = (newOne + step)%len(fl)
        self.loadSet(r,newname)

    def loadSet(self,raw,newname):
        self.wavname = newname[:-3]+"WAV"
        #print "New wavname:",self.wavname
        """
        else:
            fn = self.wavname
            path,name = os.path.split(fn) # Correct for files and CDNG dirs
            wv = [f for f in os.listdir(path) if f.lower().endswith(".wav")]
            wv.sort()
            try:
                current = wv.index(name)
                newOne = (current + step)%len(wv)
                newname = os.path.join(path,wv[newOne])
                self.wavname = newname
            except:
                self.wavname = newname[:-3]+".WAV"
        """
        self.audio.stop()
        self.demosaic.free() # Release textures
        self.wav = None
        self.raw.close()
        self.raw = raw
        self.playFrame = self.raw.firstFrame
        self.frameCache = {0:self.raw.firstFrame}
        self.preloadingFrame = 0
        self.preloadingFrames = []
        self.playTime = 0
        self.playFrameNumber = 0
        self.nextFrameNumber = 0
        self.neededFrame = 0
        self.drawnFrameNumber = None
        self.playFrame = self.raw.firstFrame
        self.preloadFrame(1) # Immediately try to preload the next frame
        self.indexing = True
        self.markReset()
        self._init = False
        self.init()
        self.refresh()

    def drop(self,objects):
        # Drag and drop from the system! Not drop-frames
        fn = objects[0]
        r = MlRaw.loadRAWorMLV(fn)
        if r:
            self.loadSet(r,fn)

    def windowName(self):
        #try:
        return "MlRawViewer v"+config.versionString()+" - "+self.raw.description()
        #except:
        #    return "MlRawViewer v"+version
    def init(self):
        if self._init: return
        if self.svbo == None:
            self.svbo = ui.SharedVbo()
        self.scenes = []
        if self.demosaic == None:
            self.demosaic = DemosaicScene(self.raw,self,self,self,size=(self.raw.width(),self.raw.height()))
        else:
            self.demosaic.initTextures()
        self.scenes.append(self.demosaic)
        if self.display == None:
            self.display = DisplayScene(self,size=(0,0))
        self.display.setRgbImage(self.demosaic.rgbImage)
        self.scenes.append(self.display)
        self.rgbImage = self.demosaic.rgbImage
        self.initWav()
        self.vidAspectHeight = float(self.raw.height())/(self.raw.width()) # multiply this number on width to give height in aspect
        self.vidAspectWidth = float(self.raw.width())/(self.raw.height()) # multiply this number on height to give height in aspect
        self._init = True
    def onDraw(self,width,height):
        # First convert Raw to RGB image at same size
        PLOG(PLOG_FRAME,"onDraw start")
        self.init()
        if self._isFull != self.wasFull:
            GLCompute.reset_state()
            self.svbo.bound = False
            self.wasFull = self._isFull
        if not self.svbo.bound:
            self.svbo.bind()
        if self.realStartTime == None or self.raw.indexingStatus()<1.0:
            offset = self.playFrameNumber / self.fps
            self.realStartTime = time.time() - offset
            PLOG(PLOG_FRAME,"realStartTime set to %f"%self.realStartTime)
        aspectHeight = int((width*self.vidAspectHeight))
        aspectWidth = int((height*self.vidAspectWidth))
        if self.anamorphic == True:
            aspectHeight = int(aspectHeight*1.4)
            aspectWidth = int(aspectWidth/1.4)
        if height > aspectHeight:
            self.display.setSize(width,aspectHeight)
            self.display.setPosition(0, height/2 - aspectHeight/2)
        else:
            self.display.setSize(aspectWidth,height)
            self.display.setPosition(width/2 - aspectWidth/2, 0)
        self.renderScenes()
        """ 
        now = time.time()
        if self.fpsMeasure == None:
            self.fpsMeasure = now
            self.fpsCount = 0
        elif self.fpsCount == 10:
            print"READ FPS:",10.0/(now-self.fpsMeasure)
            self.fpsCount = 0
            self.fpsMeasure = now
        else:
            self.fpsCount += 1
        """
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
    def key(self,k,m):
        now = time.time()
        self.lastEventTime = now
        if k==self.KEY_SPACE:
            self.togglePlay()
        elif k==self.KEY_PERIOD: # Nudge forward one frame - best when paused
            self.jump(1)
        elif k==self.KEY_COMMA: # Nudge back on frame - best when paused
            self.jump(-1)


        elif k==self.KEY_ZERO:
            self.changeWhiteBalance(1.0, 1.0, 1.0, "Passthrough") # =passthrough
        elif k==self.KEY_ONE:
            self.changeWhiteBalance(2.0, 1.0, 2.0, "WhiteFluro")  # ~WhiteFluro
        elif k==self.KEY_TWO:
            self.changeWhiteBalance(2.0, 1.0, 1.5, "Daylight")    # ~Daylight
        elif k==self.KEY_THREE:
            self.changeWhiteBalance(2.5, 1.0, 1.5, "Cloudy ")     # ~Cloudy

        elif k==self.KEY_FOUR:
            self.changeWhiteBalance(self.setting_rgb[0]*0.9, self.setting_rgb[1], self.setting_rgb[2], "red-")
        elif k==self.KEY_SEVEN:
            self.changeWhiteBalance(self.setting_rgb[0]*1.1, self.setting_rgb[1], self.setting_rgb[2], "red+")
        elif k==self.KEY_SIX:
            self.changeWhiteBalance(self.setting_rgb[0], self.setting_rgb[1], self.setting_rgb[2]*0.9, "blue-")
        elif k==self.KEY_NINE:
            self.changeWhiteBalance(self.setting_rgb[0], self.setting_rgb[1], self.setting_rgb[2]*1.1, "blue+")
        
        # Green control is now done by modifying R/B/brightness together 
        elif k==self.KEY_FIVE:
            self.changeWhiteBalance(self.setting_rgb[0]*1.1, self.setting_rgb[1], self.setting_rgb[2]*1.1, "green-")
            self.scaleBrightness(0.9)
        elif k==self.KEY_EIGHT:
            self.changeWhiteBalance(self.setting_rgb[0]*0.9, self.setting_rgb[1], self.setting_rgb[2]*0.9, "green+")
            self.scaleBrightness(1.1)

        elif k==self.KEY_Q:
            self.toggleQuality()
        elif k==self.KEY_A:
            self.toggleAnamorphic()
        elif k==self.KEY_E:
            self.toggleEncoding()
        elif k==self.KEY_D:
            self.toggleDropFrames()
        elif k==self.KEY_T:
            self.toggleToneMapping()
        elif k==self.KEY_I:
            self.toggleLooping()

        # Mark management
        elif k==self.KEY_R:
            self.markReset()
            self.refresh()
        elif k==self.KEY_L:
            self.markNext()
        elif k==self.KEY_H:
            self.markPrev()
        elif k==self.KEY_J:
            self.markIn()
        elif k==self.KEY_K:
            self.markOut()

        elif k==self.KEY_V:
            self.slideAudio(-0.5)
        elif k==self.KEY_B:
            self.slideAudio(-(1.0/float(self.fps)))
        elif k==self.KEY_N:
            self.slideAudio(1.0/(float(self.fps)))
        elif k==self.KEY_M:
            self.slideAudio(0.5)

        elif k==self.KEY_O:
            self.loadNewRawSet(-1)
        elif k==self.KEY_P:
            self.loadNewRawSet(1)

        elif k==self.KEY_LEFT: # Left cursor
            self.jump(-self.fps) # Go back 1 second (will wrap)
        elif k==self.KEY_RIGHT: # Right cursor
            self.jump(self.fps) # Go forward 1 second (will wrap)
        elif k==self.KEY_UP: # Up cursor
            self.scaleBrightness(1.1)
        elif k==self.KEY_DOWN: # Down cursor
            self.scaleBrightness(1.0/1.1)

        else:
            super(Viewer,self).key(k,m) # Inherit standard behaviour

    def userIdleTime(self):
        now = time.time()
        return now - self.lastEventTime

    def input2d(self,x,y,buttons):
        now = time.time()
        handled = self.display.input2d(x,y,buttons)
        self.lastEventTime = now

    def scaleBrightness(self,scale):
        self.setting_brightness *= scale
        #print "Brightness",self.setting_brightness
        self.refresh()
    def checkMultiplier(self, N, MAX=8.0, MIN=0.0):
        if N > MAX:
            return MAX
        elif N < MIN:
            return MIN
        else:
            return N
    def changeWhiteBalance(self, R, G, B, Name="WB"):
        R = self.checkMultiplier(R)
        G = self.checkMultiplier(G)
        B = self.checkMultiplier(B)
        self.setting_rgb = (R, G, B)
        #print "%s:\t %.1f %.1f %.1f"%(Name, R, G, B)
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
    def toggleAnamorphic(self):
        self.anamorphic = not self.anamorphic
        self.refresh()
    def toggleToneMapping(self):
        self.setting_tonemap = (self.setting_tonemap + 1)%3
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
    def onIdle(self):
        PLOG(PLOG_FRAME,"onIdle start")
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
                #print "using frame",neededFrame
                # Yes we do. Update the frame details and queue display
                self.playFrameNumber = self.neededFrame
                self.nextFrameNumber = self.playFrameNumber + 1
                self.playTime = self.neededFrame * self.fps
                self.playFrame = self.frameCache[self.neededFrame]
                self.needsRefresh = True
                self.redisplay()
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

    def checkoutfile(self):
        if os.path.exists(self.outfilename):
            i = 1
            start = os.path.splitext(self.outfilename)[0]
            if start[-3]=='_' and start[-2].isdigit() and start[-1].isdigit():
                start = start[:-3]
            self.outfilename = start + "_%02d.MOV"%i
            while os.path.exists(self.outfilename):
                i+=1
                self.outfilename = start + "_%02d.MOV"%i
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
    def toggleEncoding(self):
        if not self.setting_encoding:
            # Start the encoding process
            now = time.time()
            startframe = self.marks[0][0]
            self.realStartTime = now - startframe / self.fps
            self.neededFrame = startframe
            self.nextFrameNumber = startframe
            self.audio.stop()
            if self.setting_dropframes:
                self.toggleDropFrames()
            self.setting_encoding = True
            self.lastEncodedFrame = None
            self.paused = False # In case we were paused
            if subprocess.mswindows:
                exe = "ffmpeg.exe"
            else:
                exe = "ffmpeg"
            localexe = os.path.join(programpath,exe)
            print localexe
            if os.path.exists(localexe):
                exe = localexe
            self.checkoutfile()
            tempwavname = None
            if self.wav:
                tempwavname = self.outfilename + ".WAV"
                self.tempEncoderWav(tempwavname,self.marks[0][0],self.marks[1][0])
            kwargs = {"stdin":subprocess.PIPE,"stdout":subprocess.PIPE,"stderr":subprocess.STDOUT}
            if subprocess.mswindows:
                su = subprocess.STARTUPINFO()
                su.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                su.wShowWindow = subprocess.SW_HIDE
                kwargs["startupinfo"] = su
            if tempwavname != None: # Includes Audio
                args = [exe,"-f","rawvideo","-pix_fmt","rgb48","-s","%dx%d"%(self.raw.width(),self.raw.height()),"-r","%.03f"%self.fps,"-i","-","-i",tempwavname,"-f","mov","-vf","vflip","-vcodec","prores_ks","-profile:v","3","-r","%.03f"%self.fps,"-acodec","copy",self.outfilename]
            else: # No audio
                args = [exe,"-f","rawvideo","-pix_fmt","rgb48","-s","%dx%d"%(self.raw.width(),self.raw.height()),"-r","%.03f"%self.fps,"-i","-","-an","-f","mov","-vf","vflip","-vcodec","prores_ks","-profile:v","3","-r","%.03f"%self.fps,self.outfilename]
            print "Encoder args:",args
            print "Subprocess args:",kwargs
            self.encoderProcess = subprocess.Popen(args,**kwargs)
            self.encoderProcess.poll()
            self.stdoutReader = Thread(target=self.stdoutReaderLoop)
            self.stdoutReader.daemon = True
            self.encoderOutput = []
            self.stdoutReader.start()
            if self.encoderProcess.returncode != None:
                self.encoderProcess = None # Failed to start encoder for some reason
                self.setting_encoding = False
        else:
            # Stop/cancel the encoding process
            self.setting_encoding = False
            if self.encoderProcess:
                self.encoderProcess.stdin.close()
                self.encoderProcess = None
                self.paused = True
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
            try:
                self.wav = wave.open(self.wavname,'r')
            except:
                self.wav = None
            #print "wav",self.wav.getparams()
            #self.startAudio()
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
        #if self.audioOffset <= 0.0:
        #    self.audioOffset = 0.0
        print "Audio offset = %.02f seconds"%self.audioOffset
        if not self.paused:
            now = time.time()
            offset = now - self.realStartTime
            self.startAudio(offset)
    def exit(self):
        self.audio.stop()
    def tempEncoderWav(self,tempname,inframe,outframe):
        """
        Create a temporary wav file starting from the current audioOffset
        Start and end frames match the given in/out marks
        outframe is included
        This will be fed as one stream to the external encoder
        """
        if not self.wav:
            return
        tempwav = wave.open(tempname,'w')
        tempwav.setparams(self.wav.getparams())
        channels,width,framerate,nframe,comptype,compname = self.wav.getparams()
        frameCount = framerate * int(float(outframe-inframe+1)/float(self.fps))
        startFrame = int((self.audioOffset+(float(inframe)/float(self.fps)))*framerate)
        padframes = 0
        readPos = startFrame
        if startFrame<0:
            padframes = -startFrame
            readPos = 0
        self.wav.setpos(readPos)
        if (startFrame+frameCount)>=(nframe):
            frames = self.wav.readframes(nframe-startFrame) # Less than all
        else:
            frames = self.wav.readframes(frameCount) # All
        if padframes>0:
            pad = "\0"*padframes*channels*width
            tempwav.writeframes(pad)
        tempwav.writeframes(frames)
        tempwav.close()

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
        if index in self.preloadingFrames:
            return # Currently being loaded
        if index in self.frameCache:
            return # Already available in the cache
        if self.preloadingFrame == 2:
            return # Don't preload more than 2 frames
        self.preloadingFrame += 1
        #print "preloading",index
        PLOG(PLOG_FRAME,"Calling preload for frame %d"%index)
        self.raw.preloadFrame(index)
        self.preloadingFrames.append(index)
        PLOG(PLOG_FRAME,"Returned from preload for frame %d"%index)
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
        if self.preloadingFrame > 0:
            if self.raw.isPreloadedFrameAvailable():
                frameIndex,preloadedFrame = self.raw.nextFrame()
                expected = self.preloadingFrames.pop(0)
                if expected != frameIndex:
                    print "!!! Received frame",frameIndex,"but expected",expected
                PLOG(PLOG_FRAME,"Received preloaded frame %d"%frameIndex)
                #print "new frame loaded:",frameIndex
                # Add it to the cache
                self.frameCache[frameIndex] = preloadedFrame
                self.manageFrameCache()
                self.preloadingFrame -= 1
        self.manageFrameLoading()
    MARK_IN = 0
    MARK_OUT = 1
    def markReset(self):
        # By default, start at start and end at end, whole file in scope
        self.marks = [(0,self.MARK_IN),(self.raw.frames()-1,self.MARK_OUT)]
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
        index = 0
        insert = True
        mark = (at,markType)
        # Find index
        for frame,kind in self.marks:
            if frame==at:
                insert = False
                break  
            elif frame>at:
                break
            index += 1
        # Do the correct operation
        if insert:
            if index==len(self.marks):
                # Adding a new mark at the end
                if kind == markType:
                    #print "replacing prev mark",index
                    self.marks[index-1] = mark
                """
                    if markType==self.MARK_IN: # Must add end as out
                        self.marks.append((self.raw.frames(),self.MARK_OUT)
                elsAe:
                """
            elif index==0:
                # Adding a new mark at the start
                if kind == markType:
                    #print "replacing next mark",index
                    self.marks[index] = mark
            elif markType == kind:
                # We are inserting same kind of mark as the one after -> replace that
                #print "replacing next mark",index
                self.marks[index] = mark
            else:
                # We are inserting same kind of mark as the previous one -> replace that
                #print "replacing prev mark",index
                self.marks[index-1] = mark
        else: 
            pass
            #if kind != markType:
            #    print "deleting mark",index
            #    del self.marks[index] 

        #print self.marks               
        self.refresh()

def main():
    if len(sys.argv)<2:
        print "Error. Please specify an MLV or RAW file to view"
        return -1
    filename = sys.argv[1]
    if not os.path.exists(filename):
        print "Error. Specified filename",filename,"does not exist"
        return -1

    # Try to pick a sensible default filename for any possible encoding
    if os.path.isdir(sys.argv[1]): # Dir - probably CDNG
        outfilename = os.path.abspath(sys.argv[1])+".MOV"
        print "outfilename for CDNG:",outfilename
    else: # File
        outfilename = sys.argv[1]+".MOV"

    poswavname = os.path.splitext(filename)[0]+".WAV"
    wavnames = [w for w in os.listdir(os.path.split(filename)[0]) if w.lower()==poswavname]
    if len(wavnames)>0:
        wavfilename = wavnames[0]
    else:
        wavfilename = poswavname # Expect this to be extracted by indexing of MLV with SND

    if len(sys.argv)==3:
        # Second arg could be WAV or outfilename
        if sys.argv[2].lower().endswith(".wav"):
            wavfilename = sys.argv[2]
        else:
            outfilename = sys.argv[2]
    elif len(sys.argv)>3:
        wavfilename = sys.argv[2]
        outfilename = sys.argv[3]

    try:
        r = MlRaw.loadRAWorMLV(filename)
        if r==None:
            sys.stderr.write("%s not a recognised RAW/MLV file or CinemaDNG directory.\n"%filename)
            return 1
    except Exception, err:
        sys.stderr.write('Could not open file %s. Error:%s\n'%(filename,str(err)))
        return 1


    rmc = Viewer(r,outfilename,wavfilename)
    ret = rmc.run()
    PerformanceLog.PLOG_PRINT()
    return ret

def launchFromGui(rawfile,outfilename=None): ##broken now
    rmc = Viewer(rawfile,outfilename)
    return rmc.run()

if __name__ == '__main__':
    sys.exit(main())
