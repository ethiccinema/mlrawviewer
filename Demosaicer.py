"""
Demosaicer.py, part of MlRawViewer
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

import time

import PerformanceLog
from PerformanceLog import PLOG
PerformanceLog.PLOG_CONTROL(False)
PLOG_FILE_IO = PerformanceLog.PLOG_TYPE(0,"FILE_IO")
PLOG_FRAME = PerformanceLog.PLOG_TYPE(1,"FRAME")
PLOG_CPU = PerformanceLog.PLOG_TYPE(2,"CPU")
PLOG_GPU = PerformanceLog.PLOG_TYPE(3,"GPU")

import GLCompute
import GLComputeUI as ui
from ShaderDemosaicNearest import *
from ShaderDemosaicBilinear import *
from ShaderDemosaicCPU import *
from ShaderPreprocess import *
from ShaderPatternNoise import *
from ShaderHistogram import *

class Demosaicer(ui.Drawable):
    def __init__(self,settings,encoder,frames,**kwds):
        super(Demosaicer,self).__init__(**kwds)
        self.shaderPatternNoise = ShaderPatternNoise()
        self.shaderPreprocess = ShaderPreprocess()
        self.shaderNormal = ShaderDemosaicBilinear()
        self.shaderQuality = ShaderDemosaicCPU()
        self.shaderHistogram = ShaderHistogram()
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

    def setTextures(self,rgbImage,horizontalPattern,verticalPattern,preprocessTex1,preprocessTex2,rawUploadTex,rgbUploadTex,histogramTex):
        self.rgbImage = rgbImage
        self.horizontalPattern = horizontalPattern
        self.verticalPattern = verticalPattern
        self.preprocessTex1 = preprocessTex1
        self.preprocessTex2 = preprocessTex2
        self.rawUploadTex = rawUploadTex
        self.rgbUploadTex = rgbUploadTex
        self.histogramTex = histogramTex
        self.lastPP = self.preprocessTex2
        self.lut = None
        self.luttex = None
        self.lut1d1 = None
        self.lut1d2 = None
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
        lut1d = self.frames.currentLut1D1()
        if lut1d != self.lut1d1:
            self.lut1d1 = lut1d
            lutchanged = True
            if self.lut1d1tex != None:
                self.lut1d1tex.free()
                self.lut1d1tex = None
        if self.lut1d1tex == None:
            l = self.lut1d1
            if l != None:
                self.lut1d1tex = GLCompute.Texture1D(l.len(),l.lut().tostring())
        lut1d2 = self.frames.currentLut1D2()
        if lut1d2 != self.lut1d2:
            self.lut1d2 = lut1d2
            lutchanged = True
            if self.lut1d2tex != None:
                self.lut1d2tex.free()
                self.lut1d2tex = None
        if self.lut1d2tex == None:
            l = self.lut1d2
            if l != None:
                self.lut1d2tex = GLCompute.Texture1D(l.len(),l.lut().tostring())
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
                    self.shaderQuality.demosaicPass(self.rgbUploadTex,self.luttex,frameData.black,balance=balance,white=frameData.white,tonemap=tone,colourMatrix=self.settings.setting_colourMatrix,lut1d1=self.lut1d1tex,lut1d2=self.lut1d2tex)
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
                    self.shaderQuality.demosaicPass(self.rgbUploadTex,self.luttex,frameData.black,balance=(newrgb[0],newrgb[1],newrgb[2],balance[3]),white=frameData.white,tonemap=tone,colourMatrix=self.settings.setting_colourMatrix,recover=0.0,lut1d1=self.lut1d1tex,lut1d2=self.lut1d2tex)
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
                    self.shaderNormal.demosaicPass(self.lastPP,self.luttex,frameData.black,balance=(1.0,1.0,1.0,balance[3]),white=frameData.white,tonemap=self.settings.tonemap(),colourMatrix=self.settings.setting_colourMatrix,recover=0.0,lut1d1=self.lut1d1tex,lut1d2=self.lut1d2tex)
                else:
                    self.shaderNormal.demosaicPass(self.rawUploadTex,self.luttex,frameData.black,balance=balance,white=frameData.white,tonemap=self.settings.tonemap(),colourMatrix=self.settings.setting_colourMatrix,lut1d1=self.lut1d1tex,lut1d2=self.lut1d2tex)
                PLOG(PLOG_GPU,"Demosaic shader draw done for frame %d"%frameNumber)
        #redframe = glReadPixels(0,10,scene.size[0],1,GL_RGB,GL_FLOAT)
        #histogram = np.histogram(redframe,bins=256)
        # Calculate histogram
        if self.frames.setting_histogram == 1:
            self.histogramTex.bindfbo()
            self.shaderHistogram.draw(scene.size[0],scene.size[1],self.rgbImage)
            """
            histogram = glReadPixels(0,0,256,1,GL_RGB,GL_UNSIGNED_SHORT)
            print histogram
            for i in range(256):
                print histogram[i],
            #print
            """

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
        self.histogramTex = GLCompute.Texture((2**7,2**3),None,hasalpha=False,mono=False,sixteen=True)
        self.demosaicer.setTextures(self.rgbImage,self.horizontalPattern,self.verticalPattern,self.preprocessTex1,self.preprocessTex2,self.rawUploadTex,self.rgbUploadTex,self.histogramTex)
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
        self.histogramTex.free()
        if self.demosaicer.luttex != None:
            self.demosaicer.luttex.free()
    def prepareToRender(self):
        self.demosaicer.shaderNormal.prepare(self.frames.svbo)
        self.demosaicer.shaderQuality.prepare(self.frames.svbo)
        self.demosaicer.shaderPreprocess.prepare(self.frames.svbo)
        self.demosaicer.shaderPatternNoise.prepare(self.frames.svbo)
        w = self.frames.raw.width()
        h = self.frames.raw.height()
        maxcount = w * h
        while maxcount > 1000000:
            w = w / 2
            maxcount = w * h
            if maxcount > 1000000:
                h = h / 2
                maxcount = w * h

        self.demosaicer.shaderHistogram.prepare(self.frames.svbo,width=w,height=h)
