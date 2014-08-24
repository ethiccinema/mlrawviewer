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
import sys,struct,os,math,time,datetime,subprocess,signal,threading,Queue,wave,zlib,array
from threading import Thread

import dialogs

import multiprocessing
import multiprocessing.queues
from multiprocessing import Process

from Config import Config

import LUT

config = Config(version=(1,2,2))
programpath = os.path.abspath(os.path.split(sys.argv[0])[0])
if getattr(sys,'frozen',False):
    programpath = sys._MEIPASS
    # Assume we have no console, so try to redirect output to a log file...somewhere
    try:
        sys.stdout = file(config.logFilePath(),"a")
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
from ShaderPreprocess import *
from ShaderPatternNoise import *
from ShaderText import *
import ExportQueue

ENCODE_TYPE_MOV = 0
ENCODE_TYPE_DNG = 1
ENCODE_TYPE_MAX = 2

class Demosaicer(ui.Drawable):
    def __init__(self,settings,encoder,frames,**kwds):
        super(Demosaicer,self).__init__(**kwds)
        self.shaderPatternNoise = ShaderPatternNoise()
        self.shaderPreprocess = ShaderPreprocess()
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
        self.lastPP = None

    def setTextures(self,rgbImage,horizontalPattern,verticalPattern,preprocessTex1,preprocessTex2,rawUploadTex,rgbUploadTex):
        self.rgbImage = rgbImage
        self.horizontalPattern = horizontalPattern
        self.verticalPattern = verticalPattern
        self.preprocessTex1 = preprocessTex1
        self.preprocessTex2 = preprocessTex2
        self.rawUploadTex = rawUploadTex
        self.rgbUploadTex = rgbUploadTex
        self.lastPP = self.preprocessTex2
        self.lut = None
        self.luttex = None
        self.lut1d1tex = None
        self.lut1d2tex = None

    def render(self,scene,matrix,opacity):
        lut = self.frames.currentLut3D()
        lutchanged = False
        if lut != self.lut:
            self.lut = lut
            lutchanged = True
            if self.luttex != None:
                self.luttex.free()
                self.luttex = None
        if self.luttex == None:
            l = self.lut
            if l != None:
                self.luttex = GLCompute.Texture3D(l.len(),l.lut().tostring())
        #if self.lut1d1tex == None:
        #    l = LUT.LOG_1D_LUT
        #    self.lut1d1tex = GLCompute.Texture1D(l.len(),l.lut().tostring())
        frameData = self.frames.currentFrame()
        frameNumber = self.frames.currentFrameNumber()

        #r1 = 1.0
        #g1 = 0.5
        #b1 = 0.1
        #testrgb = np.array([r1,g1,b1])
        #testrgb2 = np.dot(camToLinearsRGB,testrgb)
        #print camToLinearsRGB,testrgb,testrgb2

        brightness = self.settings.brightness()
        rgb = self.settings.rgb()
        balance = (rgb[0], rgb[1], rgb[2], brightness)
        tone = self.settings.tonemap()
        different = (frameData != self.lastFrameData) or (brightness != self.lastBrightness) or (rgb != self.lastRgb) or (frameNumber != self.lastFrameNumber) or (tone != self.lastTone) or (lutchanged)
        # or (rgb[0] != frameData.rawwbal[0]) or (rgb[2] != frameData.rawwbal[2])
        if (frameData and different):
            if ((frameData.rgbimage!=None) or self.settings.highQuality() or self.settings.encoding()) and (frameData.canDemosaic):
                # Already rgb available, or else low/high quality decode for static view or encoding
                if not self.settings.setting_preprocess:
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
                    self.shaderQuality.demosaicPass(self.rgbUploadTex,self.luttex,frameData.black,balance=balance,white=frameData.white,tonemap=tone,colourMatrix=self.settings.setting_colourMatrix,lut1d1=self.lut1d1tex)
                    #mydump = glReadPixels(0,0,scene.size[0],scene.size[1],GL_RGB,GL_UNSIGNED_SHORT)
                    #print frameNumber
                    #for i in range(10):
                    #    print "(%04x,%04x,%04x)"%tuple(mydump[0,i,:]),
                    #print
                    if self.settings.encoding():
                        self.rgb = glReadPixels(0,0,scene.size[0],scene.size[1],GL_RGB,GL_UNSIGNED_SHORT)
                        self.encoder.encode(frameNumber,self.rgb)
                else: # Preprocess AND CPU demosaic
                    if frameData != self.lastFrameData:
                        PLOG(PLOG_CPU,"Bayer 14-16 convert starts for frame %d"%frameNumber)
                        frameData.convert()
                        PLOG(PLOG_CPU,"Bayer 14-16 convert done for frame %d"%frameNumber)
                        self.rawUploadTex.update(frameData.rawimage)
                    PLOG(PLOG_GPU,"Demosaic shader draw for frame %d"%frameNumber)
                    # Do some preprocess passes to find horizontal/vertical stripes
                    if frameData.rgbimage == None:
                        self.horizontalPattern.bindfbo()
                        self.shaderPatternNoise.draw(scene.size[0],scene.size[1],self.rawUploadTex,0,frameData.black/65536.0,frameData.white/65536.0)
                        ssh = self.shaderPatternNoise.calcStripescaleH(scene.size[0],scene.size[1])
                        self.verticalPattern.bindfbo()
                        self.shaderPatternNoise.draw(scene.size[0],scene.size[1],self.rawUploadTex,1,frameData.black/65536.0,frameData.white/65536.0)
                        ssv = self.shaderPatternNoise.calcStripescaleV(scene.size[0],scene.size[1])
                        if self.lastPP == self.preprocessTex2:
                            self.preprocessTex1.bindfbo()
                            self.shaderPreprocess.draw(scene.size[0],scene.size[1],self.rawUploadTex,self.preprocessTex2,self.horizontalPattern,self.verticalPattern,ssh,ssv,frameData.black/65536.0,frameData.white/65536.0,balance)
                            self.lastPP = self.preprocessTex1
                        else:
                            self.preprocessTex2.bindfbo()
                            self.shaderPreprocess.draw(scene.size[0],scene.size[1],self.rawUploadTex,self.preprocessTex1,self.horizontalPattern,self.verticalPattern,ssh,ssv,frameData.black/65536.0,frameData.white/65536.0,balance)
                            self.lastPP = self.preprocessTex2
                        # Now, read out the results as a 16bit raw image and feed to cpu demosaicer
                        rawpreprocessed = glReadPixels(0,0,scene.size[0],scene.size[1],GL_RED,GL_UNSIGNED_SHORT)
                        frameData.rawimage = rawpreprocessed
                        frameData.rawwbal = balance[:3]
                        self.rgbImage.bindfbo()
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
                    newrgb = (rgb[0]/frameData.rawwbal[0],1.0,rgb[2]/frameData.rawwbal[2])
                    self.shaderQuality.demosaicPass(self.rgbUploadTex,self.luttex,frameData.black,balance=(newrgb[0],newrgb[1],newrgb[2],balance[3]),white=frameData.white,tonemap=tone,colourMatrix=self.settings.setting_colourMatrix,recover=0.0,lut1d1=self.lut1d1tex)
            else:
                # Fast decode for full speed viewing
                if frameData != self.lastFrameData:
                    PLOG(PLOG_CPU,"Bayer 14-16 convert starts for frame %d"%frameNumber)
                    frameData.convert()
                    PLOG(PLOG_CPU,"Bayer 14-16 convert done for frame %d"%frameNumber)
                    self.rawUploadTex.update(frameData.rawimage)
                PLOG(PLOG_GPU,"Demosaic shader draw for frame %d"%frameNumber)

                if self.settings.setting_preprocess:
                    # Do some preprocess passes to find horizontal/vertical stripes
                    self.horizontalPattern.bindfbo()
                    self.shaderPatternNoise.draw(scene.size[0],scene.size[1],self.rawUploadTex,0,frameData.black/65536.0,frameData.white/65536.0)
                    ssh = self.shaderPatternNoise.calcStripescaleH(scene.size[0],scene.size[1])
                    self.verticalPattern.bindfbo()
                    self.shaderPatternNoise.draw(scene.size[0],scene.size[1],self.rawUploadTex,1,frameData.black/65536.0,frameData.white/65536.0)
                    ssv = self.shaderPatternNoise.calcStripescaleV(scene.size[0],scene.size[1])
                    # Swap preprocess buffer - feed previous one to new call
                    if self.lastPP == self.preprocessTex2:
                        self.preprocessTex1.bindfbo()
                        self.shaderPreprocess.draw(scene.size[0],scene.size[1],self.rawUploadTex,self.preprocessTex2,self.horizontalPattern,self.verticalPattern,ssh,ssv,frameData.black/65536.0,frameData.white/65536.0,balance)
                        self.lastPP = self.preprocessTex1
                    else:
                        self.preprocessTex2.bindfbo()
                        self.shaderPreprocess.draw(scene.size[0],scene.size[1],self.rawUploadTex,self.preprocessTex1,self.horizontalPattern,self.verticalPattern,ssh,ssv,frameData.black/65536.0,frameData.white/65536.0,balance)
                        self.lastPP = self.preprocessTex2
                    #debug = glReadPixels(0,0,16,16,GL_RGBA,GL_FLOAT)
                    #print debug
                    self.rgbImage.bindfbo()
                    self.shaderNormal.demosaicPass(self.lastPP,self.luttex,frameData.black,balance=(1.0,1.0,1.0,balance[3]),white=frameData.white,tonemap=self.settings.tonemap(),colourMatrix=self.settings.setting_colourMatrix,recover=0.0,lut1d1=self.lut1d1tex)
                else:
                    self.shaderNormal.demosaicPass(self.rawUploadTex,self.luttex,frameData.black,balance=balance,white=frameData.white,tonemap=self.settings.tonemap(),colourMatrix=self.settings.setting_colourMatrix,lut1d1=self.lut1d1tex)
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
        self.horizontalPattern = GLCompute.Texture((raw.width(),1),None,hasalpha=False,mono=False,fp=True)
        self.verticalPattern = GLCompute.Texture((1,raw.height()),None,hasalpha=False,mono=False,fp=True)
        zero = "\0"*raw.width()*raw.height()*2*4 # 16bit RGBA
        self.preprocessTex1 = GLCompute.Texture((raw.width(),raw.height()),zero,hasalpha=True,mono=False,sixteen=True)
        self.preprocessTex2 = GLCompute.Texture((raw.width(),raw.height()),zero,hasalpha=True,mono=False,sixteen=True)
        #try: self.rgbUploadTex = GLCompute.Texture((self.raw.width(),self.raw.height()),None,hasalpha=False,mono=False,fp=True)
        self.rgbUploadTex = GLCompute.Texture((raw.width(),raw.height()),None,hasalpha=False,mono=False,sixteen=True)
        try: self.rgbImage = GLCompute.Texture((raw.width(),raw.height()),None,hasalpha=False,mono=False,fp=True)
        except GLError: self.rgbImage = GLCompute.Texture((raw.width(),raw.height()),None,hasalpha=False,sixteen=True)
        self.demosaicer.setTextures(self.rgbImage,self.horizontalPattern,self.verticalPattern,self.preprocessTex1,self.preprocessTex2,self.rawUploadTex,self.rgbUploadTex)
        #print "Using",self.demosaicer.shaderNormal.demosaic_type,"demosaic algorithm"
    def setTarget(self):
        self.rgbImage.bindfbo()
    def free(self):
        self.horizontalPattern.free()
        self.verticalPattern.free()
        self.preprocessTex1.free()
        self.preprocessTex2.free()
        self.rawUploadTex.free()
        self.rgbUploadTex.free()
        self.rgbImage.free()
        if self.demosaicer.luttex != None:
            self.demosaicer.luttex.free()
    def prepareToRender(self):
        self.demosaicer.shaderNormal.prepare(self.frames.svbo)
        self.demosaicer.shaderQuality.prepare(self.frames.svbo)
        self.demosaicer.shaderPreprocess.prepare(self.frames.svbo)
        self.demosaicer.shaderPatternNoise.prepare(self.frames.svbo)

class Display(ui.Drawable):
    def __init__(self,**kwds):
        super(Display,self).__init__(**kwds)
        self.displayShader = ShaderDisplaySimple()
    def setRgbImage(self,rgbImage):
        self.rgbImage = rgbImage
    def render(self,scene,matrix,opacity):
        # Now display the RGB image
        #self.rgbImage.addmipmap()
        # Scale
        PLOG(PLOG_GPU,"Display shader draw")
        #print scene.frames.raw.activeArea
        #print scene.frames.raw.cropOrigin
        #print scene.frames.raw.cropSize
        aa = scene.frames.raw.activeArea
        fw = scene.frames.raw.width()
        fh = scene.frames.raw.height()
        tlx,tly = aa[1],aa[0]
        aw = aa[3]-aa[1]
        ah = aa[2]-aa[0]
        if aw>=fw:
            aw = fw
            tlx = 0
        if ah>=fh:
            ah = fh
            tly = 0
        self.displayShader.draw(scene.size[0],scene.size[1],self.rgbImage,(tlx,tly,aw,ah))
        PLOG(PLOG_GPU,"Display shader draw done")
        # 1 to 1
        #self.displayShader.draw(self.rgbImage.width,self.rgbImage.height,self.rgbImage)

class DisplayScene(ui.Scene):
    def __init__(self,frames,**kwds):
        super(DisplayScene,self).__init__(**kwds)
        self.dropperActive = False
        self.frames = frames # Frames interface
        self.icons = zlib.decompress(file(os.path.join(programpath,"data/icons.z"),'rb').read())
        self.iconsz = int(math.sqrt(len(self.icons)))
        self.icontex = GLCompute.Texture((self.iconsz,self.iconsz),rgbadata=self.icons,hasalpha=False,mono=True,sixteen=False,mipmap=True)
        self.display = Display()
        self.iconBackground = ui.Geometry(svbo=frames.svbo)
        self.iconBackground.edges = (1.0,1.0,0.35,0.25)
        self.mark = ui.Geometry(svbo=frames.svbo)
        self.mark.edges = (1.0,1.0,0.01,0.6)
        self.mark.colour = (0.85,0.35,0.20,0.85) # Quite transparent yellow
        self.progressBackground = ui.Geometry(svbo=frames.svbo)
        self.progressBackground.edges = (1.0,1.0,0.01,0.25)
        self.progress = ui.Button(0,0,self.progressClick,svbo=frames.svbo)
        self.progress.edges = (1.0,1.0,0.01,0.5)
        self.play = self.newIcon(0,0,128,128,0,self.playClick,"Pause or Play the current clip (Key:SPACE)")
        self.play.colour = (0.5,0.5,0.5,0.5) # Quite transparent white
        self.quality = self.newIcon(0,0,128,128,5,self.qualityClick,"Quality of preview debayering - Bilinear or AMaZE (Key:Q)")
        self.quality.colour = (0.5,0.5,0.5,0.5) # Quite transparent white
        self.quality.setScale(0.25)
        self.stripes = self.newIcon(0,0,128,128,22,self.stripesClick,"Status of stripe correction (X means active) - (Key:0)")
        self.stripes.colour = (0.5,0.5,0.5,0.5) # Quite transparent white
        self.stripes.setScale(0.25)
        self.drop = self.newIcon(0,30,128,128,7,self.dropClick,"Drop-frames to keep frame rate (clock) or show all frames (Key:F)")
        self.drop.colour = (0.5,0.5,0.5,0.5) # Quite transparent white
        self.drop.setScale(0.25)
        self.fullscreen = self.newIcon(0,60,128,128,9,self.fullscreenClick,"Toggle Fullscreen view (Key:TAB)")
        self.fullscreen.colour = (0.5,0.5,0.5,0.5) # Quite transparent white
        self.fullscreen.setScale(0.25)
        self.mapping = self.newIcon(0,90,128,128,11,self.mappingClick,"Tone mapping - sRGB,R709,Linear,LOG,HDR (Key:T)")
        self.mapping.colour = (0.5,0.5,0.5,0.5) # Quite transparent white
        self.mapping.setScale(0.25)
        self.update = self.newIcon(0,0,128,128,16,self.updateClick,"New version of MlRawViewer is available. Click to download")
        self.update.colour = (0.5,0.1,0.0,0.5)
        self.update.setScale(0.5)
        self.loop = self.newIcon(0,0,128,128,17,self.loopClick,"Loop clip or play once (Key:L)")
        self.loop.colour = (0.5,0.5,0.5,0.5)
        self.loop.setScale(0.5)
        self.outformat = self.newIcon(0,0,128,128,19,self.outfmtClick,"Export format - MOV or DNG (Key:D)")
        self.outformat.colour = (0.5,0.5,0.5,0.5)
        self.outformat.setScale(0.5)
        self.addencode = self.newIcon(0,0,128,128,21,self.addEncodeClick,"Add clip to export queue (Key:E)")
        self.addencode.colour = (0.5,0.5,0.5,0.5)
        self.addencode.setScale(0.5)

        self.cidropper = self.newIcon(0,0,128,128,24,self.ciDropperClick,"Choose white balance from neutral object")
        self.cidropper.colour = (0.5,0.5,0.5,0.5)
        self.cidropper.setScale(0.25)
        self.cievzero = self.newIcon(0,0,128,128,25,self.ciEvzeroClick,"Reset exposure to zero EV")
        self.cievzero.colour = (0.5,0.5,0.5,0.5)
        self.cievzero.setScale(0.25)
        self.ciundo = self.newIcon(0,0,128,128,26,self.ciUndoClick,"Undo colour/exposure change")
        self.ciundo.colour = (0.5,0.5,0.5,0.5)
        self.ciundo.setScale(0.25)
        self.ciredo = self.newIcon(0,0,128,128,27,self.ciRedoClick,"Redo colour/exposure change")
        self.ciredo.colour = (0.5,0.5,0.5,0.5)
        self.ciredo.setScale(0.25)
        self.cistore = self.newIcon(0,0,128,128,28,self.ciStoreClick,"Store current colour/exposure (Key:H)")
        self.cistore.colour = (0.5,0.5,0.5,0.5)
        self.cistore.setScale(0.25)
        self.cirecall = self.newIcon(0,0,128,128,29,self.ciRecallClick,"Recall current colour/exposure (Key:G)")
        self.cirecall.colour = (0.5,0.5,0.5,0.5)
        self.cirecall.setScale(0.25)
        self.ciItems = [self.cievzero,self.cidropper,self.ciundo,self.ciredo,self.cistore,self.cirecall]
        #self.encodeStatus = ui.Geometry(svbo=frames.svbo)
        self.balance = ui.XYGraph(128,128,self.balanceClick,svbo=self.frames.svbo)
        self.balance.gradient(128,128,tl=(0.25,0.0,0.0,0.25),tr=(0.25,0.0,0.25,0.25),bl=(0.0,0.0,0.0,0.25),br=(0.0,0.0,0.25,0.25))
        self.balance.edges = (1.0,1.0,0.05,0.05)
        self.balanceHandle = self.newIcon(0,0,8,8,2,None)
        self.balanceHandle.colour = (0.5,0.5,0.5,0.5)
        self.balanceHandle.ignoreInput = True
        self.whitePicker = ui.XYGraph(self.size[0],self.size[1],self.whiteClick,svbo=self.frames.svbo)
        self.brightness = ui.XYGraph(32,128,self.brightnessClick,svbo=self.frames.svbo)
        self.brightness.gradient(32,128,tl=(0.25,0.25,0.25,0.25),tr=(0.25,0.25,0.25,0.25),bl=(0.0,0.0,0.0,0.25),br=(0.0,0.0,0.0,0.25))
        self.brightness.edges = (1.0,1.0,0.2,0.05)
        self.brightnessHandle = self.newIcon(0,0,8,8,2,None)
        self.brightnessHandle.colour = (0.5,0.5,0.5,0.5)
        self.brightnessHandle.ignoreInput = True
        self.mdbg = ui.Geometry(svbo=frames.svbo)
        self.mdbg.edges = (1.0,1.0,0.05,0.10)
        self.metadata = ui.Text("",svbo=self.frames.svbo)
        self.metadata.setScale(0.25)
        self.metadata.ignoreInput = True
        self.coldata = ui.Text("",svbo=self.frames.svbo)
        self.coldata.setScale(0.18)
        self.coldata.ignoreInput = True
        self.coldata.maxchars = 9
        self.tooltip = ui.Text("",svbo=self.frames.svbo)
        self.tooltip.setScale(0.25)
        self.tooltip.maxchars = 70
        self.tooltip.colour = (1.0,0.9,0.9,1.0)
        self.ttbg = ui.Geometry(svbo=frames.svbo)
        self.ttbg.edges = (1.0,1.0,0.05,0.3)
        self.exportq = ui.Flickable(400.0,200.0,svbo=frames.svbo)
        self.exportq.edges = (1.0,1.0,0.01,0.01)
        self.exportq.colour = (1.0,1.0,1.0,1.0)
        self.exportq.clip = True
        self.exportq.allowx = False
        self.exportqlist = ui.Text("",svbo=self.frames.svbo)
        self.exportqlist.setScale(0.25)
        self.exportq.children.append(self.exportqlist)
        self.timestamp = ui.Geometry(svbo=frames.svbo)
        self.iconItems = [self.fullscreen,self.mapping,self.drop,self.quality,self.stripes,self.loop,self.outformat,self.addencode,self.play]
        self.overlay = [self.iconBackground,self.progressBackground,self.progress,self.timestamp,self.update,self.balance,self.balanceHandle,self.brightness,self.brightnessHandle,self.mark,self.mdbg,self.metadata,self.exportq,self.coldata,self.ttbg,self.tooltip]
        self.overlay.extend(self.iconItems)
        self.overlay.extend(self.ciItems)
        self.overlay.append(self.whitePicker) # So it is on the bottom
        self.drawables.extend([self.display])
        self.drawables.extend(self.overlay)
        self.timeline = ui.Timeline()
        self.fadeAnimation = ui.Animation(self.timeline,1.0)
        self.clearhover = self.clearTooltip

    def clearTooltip(self):
        self.tooltip.text = ""

    def updateTooltip(self,button,tiptext):
        self.tooltip.text = tiptext

    def isDirty(self):
        dirty = False
        for d in self.drawables:
            if d.matrixDirty: dirty = True
        return dirty

    def setRgbImage(self,rgbImage):
        self.display.setRgbImage(rgbImage)

    def whiteClick(self,x,y,down):
        if self.dropperActive:
            self.frames.useWhitePoint(float(x)/float(self.size[0])*self.frames.raw.width(),float(y)/float(self.size[1])*self.frames.raw.height())

    def progressClick(self,x,y):
        targetFrame = self.frames.raw.frames()*(float(x)/float(self.progress.size[0]))
        #print "Progress click",x,y,"targetFrame",targetFrame
        self.frames.jumpTo(targetFrame)

    def updateClick(self,x,y):
        global config
        import webbrowser
        webbrowser.open("https://bitbucket.org/baldand/mlrawviewer/downloads")
        config.updateClickedNow()

    def balanceClick(self,x,y,down):
        r = 4.0*(1.0-y/128.0)
        b = 4.0*(x/128.0)
        g = 1.0
        self.frames.changeWhiteBalance(r,g,b,"%f,%f,%f"%(r,g,b),not down)
        if self.frames.paused:
            self.frames.refresh()

    def brightnessClick(self,x,y,down):
        b = 15.0*(1.0-y/128.0)-5.0
        b2 = math.pow(2.0,b)
        self.frames.setBrightness(b2,not down)

    def playClick(self,x,y):
        self.frames.togglePlay()

    def ciEvzeroClick(self,x,y):
        self.frames.setBrightness(1.0)

    def ciDropperClick(self,x,y):
        self.dropperActive = not self.dropperActive
        if self.frames.paused:
            self.frames.refresh()
    def ciUndoClick(self,x,y):
        self.frames.colourUndo()
    def ciRedoClick(self,x,y):
        self.frames.colourRedo()
    def ciStoreClick(self,x,y):
        self.frames.saveBalance()
    def ciRecallClick(self,x,y):
        self.frames.loadBalance()

    def loopClick(self,x,y):
        self.frames.toggleLooping()

    def mappingClick(self,x,y):
        self.frames.toggleToneMapping()

    def fullscreenClick(self,x,y):
        self.frames.toggleFullscreen()

    def qualityClick(self,x,y):
        self.frames.toggleQuality()

    def stripesClick(self,x,y):
        self.frames.toggleStripes()

    def dropClick(self,x,y):
        self.frames.toggleDropFrames()

    def outfmtClick(self,x,y):
        self.frames.toggleEncodeType()

    def encodeClick(self,x,y):
        self.frames.toggleEncoding()

    def addEncodeClick(self,x,y):
        self.frames.addEncoding()

    def newIcon(self,x,y,w,h,idx,cb,tip=""):
        icon = ui.Button(w,h,cb,svbo=self.frames.svbo,onhover=self.updateTooltip,onhoverobj=tip)
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
        states = [not f._isFull,f.tonemap(),not f.dropframes(),f.setting_highQuality,f.setting_preprocess,not f.setting_loop,f.setting_encodeType[0],False,False,f.paused]
        for i in range(len(self.iconItems)):
            itm = self.iconItems[i]
            state = states[i]
            if state!=int(state):
                if state: state = 1
                else: state = 0
            self.setIcon(itm,128,128,itm.idx+state)
        if self.dropperActive:
            self.cidropper.colour = (1.0,0.0,0.0,0.5)
        else:
            self.cidropper.colour = (0.5,0.5,0.5,0.5)
        #if self.exporter.busy:
        #    for index in self.exporter.jobs.keys():
        #        print "export",index,self.exporter.status(index)

    def summariseColdata(self):
        b = math.log(self.frames.setting_brightness,2.0)
        return "EV: %+0.3f"%b

    def summariseMetadata(self):
        r = self.frames.raw
        f = self.frames.playFrame
        s = r.make()+" "+r.model()
        if f.lens != None:
            s += ", "+f.lens[0]+"\n"
        else:
            s += "\n"
        if f.expo != None and f.lens != None:
            ll = "%d"%f.lens[2][1]
            s += "1/%d sec, f%.01f, ISO %d, %dmm\n"%(1000000.0/f.expo[-1],f.lens[2][3]/100.0,f.expo[2],f.lens[2][1])
        fpsover = self.frames.setting_fpsOverride
        if fpsover != None:
            s += "%d x %d, %.03f FPS (Was %.03f FPS)"%(r.width(),r.height(),fpsover,r.fps)
        else:
            s += "%d x %d, %.03f FPS"%(r.width(),r.height(),r.fps)
        if f.rtc != None:
            se,mi,ho,da,mo,ye = f.rtc[1:7]
            s += ", %02d:%02d:%02d %02d:%02d:%04d"%(ho,mi,se,da,mo+1,ye+1900)
        if self.frames.setting_lut3d != None:
            s += "\n3D LUT:%s"%self.frames.setting_lut3d.name()
        return s
        #make = self.frames.raw.
        #self.frames.playFrame.

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
        elif idle<=5.0:
            self.frames.setCursorVisible(True)
            if self.fadeAnimation.targval == 0.0:
                self.fadeAnimation.setTarget(1.0,0.5,0.0,ui.Animation.SMOOTH)
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
        self.whitePicker.setPos(0,0)
        self.whitePicker.size = self.size
        rtl,rtr = (width-128.0-10.0-32.0-10.0,height-rectHeight-10.0-128.0-5.0)
        self.brightness.setPos(rtl,rtr)
        b = math.log(self.frames.setting_brightness,2.0)
        b2 = 128.0-128.0*((b+5.0)/15.0)
        self.brightnessHandle.setPos(rtl+16.0-4.0,rtr+b2-4.0)
        base = rtl+4.0
        iconSpacing = 28.0
        for i in self.ciItems:
            i.setScale(0.18)
            i.setPos(base,rtr-24.0)
            base += iconSpacing
        self.updateIcons()
        fw = self.frames.raw.frames()-1
        if fw==0: fw=1
        progWidth = (float(frameNumber)/float(fw))*rectWidth
        self.progress.size = (rectWidth,rectHeight) # For input checking
        self.progress.rectangle(progWidth,rectHeight,rgba=(0.2,0.2,0.01,0.2))
        self.timestamp.setPos(66.0,height-rectHeight-1.0)
        self.timestamp.setScale(9.0/30.0)
        #self.encodeStatus.setPos(66.0,height-rectHeight-41.0)
        #self.encodeStatus.setScale(9.0/30.0)
        totsec = float(frameNumber)/self.frames.raw.fps
        minutes = int(totsec/60.0)
        seconds = int(totsec%60.0)
        fsec = (totsec - int(totsec))*1000.0
        # NOTE: We use one-based numbering for the frame number display because it is more natural -> ends on last frame
        if self.frames.raw.indexingStatus()==1.0:
            self.timestamp.label("%02d:%02d.%03d (%d/%d)"%(minutes,seconds,fsec,frameNumber+1,self.frames.raw.frames()),maxchars=100)
        else:
            self.timestamp.label("%02d:%02d.%03d (%d/%d) Indexing %s: %d%%"%(minutes,seconds,fsec,frameNumber+1,self.frames.raw.frames(),self.frames.raw.description(),self.frames.raw.indexingStatus()*100.0),maxchars=100)
        self.timestamp.colour = (0.0,0.0,0.0,1.0)
        self.metadata.setPos(66.0,10.0)
        self.metadata.text = self.summariseMetadata()
        self.metadata.update()
        self.tooltip.setPos(66.0,rtr+115.0)
        self.tooltip.update()
        self.ttbg.setPos(60.0,rtr+112.0)
        if len(self.tooltip.text)>0:
            self.ttbg.rectangle(self.tooltip.size[0]+10.0,self.tooltip.size[1]+6.0,rgba=(0.0,0.0,0.0,0.25))
        else:
            self.ttbg.rectangle(0,0,rgba=(0.0,0.0,0.0,0.25))
        self.coldata.text = self.summariseColdata()
        self.coldata.update()
        self.coldata.setPos(rtl+4.0,rtr+126.0)
        self.coldata.text = self.summariseColdata()
        self.coldata.update()
        self.mdbg.setPos(54.0,4.0)
        self.mdbg.rectangle(self.metadata.size[0]+24.0,self.metadata.size[1]+12.0,rgba=(0.0,0.0,0.0,0.25))

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

        jix = self.frames.exporter.jobs.keys()
        jix.sort()
        exports = ""
        for ix in jix:
            if len(exports)>0:
                exports += "\n"
            job = self.frames.exporter.jobs[ix]
            jobtype = job[1]
            if jobtype == ExportQueue.ExportQueue.JOB_DNG:
                rfile = os.path.split(job[2])[1]
                targ = os.path.split(job[3])[1]
                start,end = job[5:7]
            elif jobtype == ExportQueue.ExportQueue.JOB_MOV:
                rfile = os.path.split(job[2])[1]
                targ = os.path.split(job[3])[1]
                start,end = job[5:7]
            if end==None:
                jobinfo = rfile+" to "+targ+": %.02f%%"%(100.0*self.frames.exporter.status(ix),)
            else:
                jobinfo = rfile+" %d:%d to "%(start+1,end+1)+targ+": %.02f%%"%(100.0*self.frames.exporter.status(ix),)
            exports += jobinfo
        self.exportqlist.text = exports
        self.exportqlist.update()
        if len(exports)==0:
            self.exportq.opacity = 0.0
        else:
            self.exportq.opacity = self.overlayOpacity
            mlh = height-12.0-rectHeight-5.0-self.metadata.size[1]-20.0
            lh = min(self.exportqlist.size[1]+12.0,mlh)
            self.exportq.setPos(60.0,height-lh-rectHeight-5.0-30.0)
            self.exportq.rectangle(self.exportqlist.size[0]+12.0,lh,rgba=(0.0,0.0,0.0,0.25))
            self.exportq.size = (self.exportqlist.size[0]+12.0,lh)
            self.exportqlist.setPos(6.0,6.0)

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
        self.colourUndoStack = []
        self.colourRedoStack = []
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
        self.preloadingFrame = []
        self.preloadingFrames = []
        self.preloadFrame(1) # Immediately try to preload the next frame
        self.paused = False
        self.needsRefresh = False
        self.anamorphic = False # Canon squeeze
        self.anamorLens = 0 # Lens squeeze
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
        self.audioOffset = self.raw.getMeta("audioOffset_v1")
        if self.audioOffset == None: self.audioOffset = 0.0
        self.lastEventTime = time.time()
        self.wasFull = False
        self.demosaic = None
        self.markLoad()
        # Shared settings
        self.initFps()
        self.setting_rgb = (2.0, 1.0, 1.5)
        self.setting_highQuality = False
        self.setting_encoding = False
        self.setting_tonemap = 3 # 0 = Linear, 1 = Global tone map, 2 = Log, 3 = sRGB Gamma, 4 = Rec.709 Gamma
        self.setting_dropframes = True # Real time playback by default
        self.setting_loop = config.getState("loopPlayback")
        self.setting_colourMatrix = np.matrix(np.eye(3))
        self.setting_preprocess = config.getState("preprocess")
        if self.setting_preprocess == None:
	        self.setting_preprocess = False
        self.updateColourMatrix()
        if self.setting_loop == None: self.setting_loop = True
        self.setting_encodeType = config.getState("encodeType")
        if self.setting_encodeType == None: self.setting_encodeType = (ENCODE_TYPE_MOV,)
        self.svbo = None
        self.fpsMeasure = None
        self.fpsCount = 0

        self.exporter = ExportQueue.ExportQueue(config)
        self.wasExporting = False
        self.exportActive = False
        self.exportLastStatus = 0.0
        self.toggleEncoding() # On by default
        self.lutindex = 0
    def initFps(self):
        self.fps = self.raw.fps
        self.setting_fpsOverride = self.raw.getMeta("fpsOverride_v1")
        if self.setting_fpsOverride != None:
            self.fps = self.setting_fpsOverride

    def candidatesInDir(self,fn):
        path,name = os.path.split(fn) # Correct for files and CDNG dirs
        fl = [f for f in os.listdir(path) if f.lower().endswith(".mlv") or f.lower().endswith(".raw")]
        dirs = [f for f in os.listdir(path) if os.path.isdir(os.path.join(path,f))]
        cdngs = [f for f in dirs if len([d for d in os.listdir(os.path.join(path,f)) if d.lower().endswith(".dng")])]
        fl.extend(cdngs)
        fl.sort()
        return fl

    def loadNewRawSet(self,step):
        fn = self.raw.filename
        path,name = os.path.split(fn) # Correct for files and CDNG dirs
        if len(name)==0:
            path,name = os.path.split(path)
        fl = self.candidatesInDir(fn)
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
        self.colourUndoStack = []
        self.colourRedoStack = []
        self.audio.stop()
        self.demosaic.free() # Release textures
        self.wav = None
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
            self.demosaic.setSize(self.raw.width(),self.raw.height())
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
            GLCompute.SharedContextState.reset_state()
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
            self.changeWhiteBalance(2.0, 1.0, 2.0, "WhiteFluro")  # ~WhiteFluro
        elif k==self.KEY_TWO:
            self.changeWhiteBalance(2.0, 1.0, 1.5, "Daylight")    # ~Daylight
        elif k==self.KEY_THREE:
            self.changeWhiteBalance(2.5, 1.0, 1.5, "Cloudy ")     # ~Cloudy

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
            self.toggleToneMapping()
        elif k==self.KEY_L:
            self.toggleLooping()

        elif k==self.KEY_G:
            self.loadBalance()
        elif k==self.KEY_H:
            self.saveBalance()

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
            self.askOutput()

        elif k==self.KEY_Z:
            self.exporter.cancelAllJobs()
            self.refresh()
        elif k==self.KEY_X:
            if self.exporter.currentjob != -1:
                self.exporter.cancelJob(self.exporter.currentjob)
            else:
                nextjobs = self.exporter.jobs.keys()
                if len(nextjobs)>0:
                    nextjobs.sort()
                    self.exporter.cancelJob(nextjobs[0])
            self.refresh()

        elif k==self.KEY_LEFT: # Left cursor
            self.jump(-self.fps) # Go back 1 second (will wrap)
        elif k==self.KEY_RIGHT: # Right cursor
            self.jump(self.fps) # Go forward 1 second (will wrap)
        elif k==self.KEY_UP: # Up cursor
            if m==0:
                self.scaleBrightness(1.1)
            elif m==1:
                self.changeLut(1)
        elif k==self.KEY_DOWN: # Down cursor
            if m==0:
                self.scaleBrightness(1.0/1.1)
            elif m==1:
                self.changeLut(-1)

        else:
            super(Viewer,self).key(k,m) # Inherit standard behaviour

    def currentLut3D(self):
        return self.setting_lut3d

    def changeLut(self,change):
        self.lutindex += change

        ix = self.lutindex%(len(LUT.LUTS)+1)
        if ix == 0:
            self.setting_lut3d = None
            #print "LUT3D disabled"
        else:
            #print "Loading LUT",LUT.LUT_FNS[ix-1]
            self.setting_lut3d = LUT.LUTS[ix-1]
        self.raw.setMeta("lut3d_v1",self.setting_lut3d)
        self.refresh()

    def userIdleTime(self):
        now = time.time()
        return now - self.lastEventTime

    def input2d(self,x,y,buttons):
        now = time.time()
        if self.display != None:
            handled = self.display.input2d(x,y,buttons)
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
    def toggleToneMapping(self):
        self.setting_tonemap = (self.setting_tonemap + 1)%5
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
        print queuedfiles
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
        Magic button for smoe workflows?
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

def openFilename(initial):
    result = launchDialog("openFilename",initial)
    return result.strip()

def main():
    filename = None
    if len(sys.argv)<2:
        #print "Error. Please specify an MLV or RAW file to view"
        #return -1
        directory = config.getState("directory")
        if directory == None:
            directory = '~'
        afile = openFilename(directory)
        if afile != None:
            filename = afile
            if afile != '':
                config.setState("directory",os.path.dirname(filename))
    if filename == None:
        filename = sys.argv[1].decode(sys.getfilesystemencoding())
    if not os.path.exists(filename):
        print "Error. Specified filename",filename,"does not exist"
        return -1

    # Try to pick a sensible default filename for any possible encoding

    outfilename = config.getState("targetDir") # Restore persisted target
    if outfilename == None:
        outfilename = os.path.split(filename)[0]
    poswavname = os.path.splitext(filename)[0]+".WAV"
    if os.path.isdir(filename):
        wavdir = filename
    else:
        wavdir = os.path.split(filename)[0]
    wavnames = [w for w in os.listdir(wavdir) if w.lower().endswith(".wav")]
    #print "wavnames",wavnames
    if os.path.isdir(filename) and len(wavnames)>0:
        wavfilename = os.path.join(wavdir,wavnames[0])
    else:
        wavfilename = poswavname # Expect this to be extracted by indexing of MLV with SND

    #print "wavfilename",wavfilename
    if len(sys.argv)==3:
        # Second arg could be WAV or outfilename
        if sys.argv[2].lower().endswith(".wav"):
            wavfilename = sys.argv[2]
        else:
            outfilename = sys.argv[2]
            config.setState("targetDir",outfilename)
    elif len(sys.argv)>3:
        wavfilename = sys.argv[2]
        outfilename = sys.argv[3]
        config.setState("targetDir",outfilename)

    try:
        r = MlRaw.loadRAWorMLV(filename)
        if r==None:
            sys.stderr.write("%s not a recognised RAW/MLV file or CinemaDNG directory.\n"%filename)
            return 1
    except Exception, err:
        import traceback
        traceback.print_exc()
        sys.stderr.write('Could not open file %s. Error:%s\n'%(filename,str(err)))
        return 1


    rmc = Viewer(r,outfilename,wavfilename)
    ret = rmc.run()
    PerformanceLog.PLOG_PRINT()
    return ret


if __name__ == '__main__':
    sys.exit(main())
