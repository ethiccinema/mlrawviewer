#!/usr/bin/python2
"""
mlrawviewer.py
(c) Andrew Baldwin 2013

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
import sys,struct,os,math,time,datetime,subprocess,signal
from threading import Thread

version = "1.0.2"

programpath = os.path.abspath(os.path.split(sys.argv[0])[0])
if getattr(sys,'frozen',False):
    programpath = sys._MEIPASS
    # Assume we have no console, so redirect output to a log file...somewhere
    sys.stdout = file("mlrawviewer.log","a")
    sys.stderr = sys.stdout

print "MlRawViewer v"+version
print "(c) Andrew Baldwin & contributors 2013"


# OpenGL. Could be missing
try:
    import OpenGL
    OpenGL.ERROR_CHECKING = False # Only for one erroneously-failing Framebuffer2DEXT call on Windows with Intel...grrr
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
import GLCompute
import MlRaw
import Font
from Matrix import *
from ShaderDemosaicNearest import *
from ShaderDemosaicBilinear import *
from ShaderDemosaicCPU import *
from ShaderDisplaySimple import *
from ShaderText import *

class Demosaicer(GLCompute.Drawable):
    def __init__(self,raw,rawUploadTex,rgbUploadTex,settings,encoder,**kwds):
        super(Demosaicer,self).__init__(**kwds)
        self.shaderNormal = ShaderDemosaicBilinear()
        self.shaderQuality = ShaderDemosaicCPU()
        self.settings = settings
        self.encoder = encoder
        self.raw = raw
        self.rawUploadTex = rawUploadTex
        self.rgbUploadTex = rgbUploadTex
    def render(self,scene):
        f = scene.frame
        frame = f 
        frameNumber = int((1*frame)/1 % self.raw.frames())
        frameData = self.raw.frame(frameNumber)
        nextFrame = int((1*(frame+1)) % self.raw.frames())
        self.raw.preloadFrame(nextFrame)
        brightness = self.settings.brightness()
        rgb = self.settings.rgb()
        balance = (rgb[0]*brightness, rgb[1]*brightness, rgb[2]*brightness)
        if (frameData):
            if (self.settings.highQuality() or self.settings.encoding()) and (frameData.canDemosaic):
                # Slow/high quality decode for static view or encoding
                before = time.time()
                frameData.demosaic()
                after = time.time()
                self.encoder.demosaicDuration(after-before)

                self.rgbUploadTex.update(frameData.rgbimage)
                self.shaderQuality.demosaicPass(self.rgbUploadTex,frameData.black,balance=balance)
        
                if self.settings.encoding():
                    self.rgb = glReadPixels(0,0,scene.size[0],scene.size[1],GL_RGB,GL_UNSIGNED_SHORT)
                    self.encoder.encode(frameNumber,self.rgb)

            else: 
                # Fast decode for full speed viewing
                frameData.convert()
                self.rawUploadTex.update(frameData.rawimage)
                self.shaderNormal.demosaicPass(self.rawUploadTex,frameData.black,balance=balance)
            

class DemosaicScene(GLCompute.Scene):
    def __init__(self,raw,settings,encoder,**kwds):
        super(DemosaicScene,self).__init__(**kwds)
        f = 0
        self.raw = raw
        self.raw.preloadFrame(f)
        print "Width:",self.raw.width(),"Height:",self.raw.height(),"Frames:",self.raw.frames()
        self.rawUploadTex = GLCompute.Texture((self.raw.width(),self.raw.height()),None,hasalpha=False,mono=True,sixteen=True)
        #try: self.rgbUploadTex = GLCompute.Texture((self.raw.width(),self.raw.height()),None,hasalpha=False,mono=False,fp=True)
        self.rgbUploadTex = GLCompute.Texture((self.raw.width(),self.raw.height()),None,hasalpha=False,mono=False,sixteen=True)
        try: self.rgbImage = GLCompute.Texture((self.raw.width(),self.raw.height()),None,hasalpha=False,mono=False,fp=True)
        except GLError: self.rgbImage = GLCompute.Texture((self.raw.width(),self.raw.height()),None,hasalpha=False,sixteen=True)
        self.demosaicer = Demosaicer(raw,self.rawUploadTex,self.rgbUploadTex,settings,encoder)
        print "Using",self.demosaicer.shaderNormal.demosaic_type,"demosaic algorithm"
        self.drawables.append(self.demosaicer)
    def setTarget(self):
        self.rgbImage.bindfbo()

class Display(GLCompute.Drawable):
    def __init__(self,rgbImage,**kwds):
        super(Display,self).__init__(**kwds)
        self.displayShader = ShaderDisplaySimple()
        self.rgbImage = rgbImage
    def render(self,scene):
        # Now display the RGB image
        #self.rgbImage.addmipmap()
        # Balance now happens in demosaicing shader
        balance = (1.0,1.0,1.0)
        # Scale
        self.displayShader.draw(scene.size[0],scene.size[1],self.rgbImage,balance)
        # 1 to 1
        # self.displayShader.draw(self.rgbImage.width,self.rgbImage.height,self.rgbImage,balance)

class Geometry(GLCompute.Drawable):
    def __init__(self,shader,**kwds):
        super(Geometry,self).__init__(**kwds)
        self.textshader = shader
        self.geometry = None
        self.matrix = Matrix4x4()
        self.colour = (1.0,1.0,1.0,1.0)
    def render(self,scene):
        if self.geometry:
            self.textshader.draw(self.geometry,self.matrix,self.colour)

class DisplayScene(GLCompute.Scene):
    def __init__(self,raw,rgbImage,font,**kwds):
        super(DisplayScene,self).__init__(**kwds)
        self.raw = raw
        self.textshader = ShaderText(font)
        self.rgbImage = rgbImage
        self.display = Display(rgbImage)
        self.progressBackground = Geometry(shader=self.textshader)
        self.progress = Geometry(shader=self.textshader)
        self.timestamp = Geometry(shader=self.textshader)
        self.drawables.extend([self.display,self.progressBackground,self.progress,self.timestamp])
    def prepareToRender(self):
        f = self.frame
        frameNumber = int(f % self.raw.frames())
        m2 = Matrix4x4()
        width,height = self.size
        m2.viewport(width,height)
        m2.translate(7.-float(width)/2.0,7.-float(height)/2.0)
        rectHeight = 0.075/(float(width)/540.0)
        rectWidth = 1.9
        self.progressBackground.geometry = self.textshader.rectangle(rectWidth,rectHeight,rgba=(0.2,0.2,0.2,0.2),update=self.progressBackground.geometry)
        self.progress.geometry = self.textshader.rectangle((float(frameNumber)/float(self.raw.frames()))*rectWidth,rectHeight,rgba=(1.0,1.0,0.2,0.2),update=self.progress.geometry)
        self.progressBackground.matrix = m2
        self.progress.matrix = m2
        m = Matrix4x4()
        m.viewport(width,height)
        m.scale(40.0*(1.0/(64.0*float(height)*(float(width)/float(height)))))
        m.translate(10.-float(width)/2.0,10.-float(height)/2.0)
        self.timestamp.matrix = m
        minutes = (frameNumber/25)/60
        seconds = (frameNumber/25)%60
        frames = frameNumber%25
        self.timestamp.geometry = self.textshader.label(self.textshader.font,"%02d:%02d.%02d"%(minutes,seconds,frames),update=self.timestamp.geometry)
        self.timestamp.colour = (0.0,0.0,0.0,1.0)

class Viewer(GLCompute.GLCompute):
    def __init__(self,raw,outfilename,**kwds):
        userWidth = 720
        self.vidAspectHeight = float(raw.height())/(raw.width()) # multiply this number on width to give height in aspect
        self.vidAspectWidth = float(raw.width())/(raw.height()) # multiply this number on height to give height in aspect
        super(Viewer,self).__init__(width=userWidth,height=int(userWidth*self.vidAspectHeight),**kwds)
        self._init = False
        self._raw = raw
        self.font = Font.Font(os.path.join(programpath,"data/os.glf"))
        self.time = 0
        self._fps = 25 # TODO - This should be read from the file
        self.paused = False
        self.needsRefresh = False
        self.anamorphic = False
        self.encoderProcess = None
        self.outfilename = outfilename
        self.lastEncodedFrame = None
        self.demosaicCount = 0
        self.demosaicTotal = 0.0
        self.demosaicAverage = 0.0
        # Shared settings
        self.setting_brightness = 50.0
        self.setting_rgb = (2.0, 1.0, 1.5)
        self.setting_highQuality = False
        self.setting_encoding = False

    def windowName(self):
        try:
            return "MlRawViewer v"+version+" - "+os.path.split(sys.argv[1])[1]
        except IndexError:
            return "MlRawViewer v"+version
    def init(self):
        if self._init: return
        self.demosaic = DemosaicScene(self._raw,self,self,size=(self._raw.width(),self._raw.height()))
        self.scenes.append(self.demosaic)
        self.display = DisplayScene(self._raw,self.demosaic.rgbImage,self.font,size=(0,0))
        self.scenes.append(self.display)
        self.rgbImage = self.demosaic.rgbImage
        self._init = True
    def onDraw(self,width,height):
        # First convert Raw to RGB image at same size
        self.init()
        aspectHeight = int((width*self.vidAspectHeight))
        aspectWidth = int((height*self.vidAspectWidth))
        if self.anamorphic == True:
            aspectHeight = int(aspectHeight*1.4)
            aspectWidth = int(aspectWidth/1.4)
        if height > aspectHeight:
            self.display.size = (width,aspectHeight)
            self.display.position = (0, height/2 - aspectHeight/2)
        else:
            self.display.size = (aspectWidth,height)
            self.display.position = (width/2 - aspectWidth/2, 0)            
        self.renderScenes()
        if self.paused:
            self._frames -= 1
    def jump(self,framesToJumpBy):
        self._frames += framesToJumpBy
        self.refresh()
    def key(self,k,x,y):
        if ord(k)==32:
            self.paused = not self.paused
            if self.paused:
                self.jump(-1) # Redisplay the current frame in high quality
                self.refresh()
        elif k=='.': # Nudge forward one frame - best when paused
            self.jump(1) 
        elif k==',': # Nudge back on frame - best when paused
            self.jump(-1)

        elif k=='1':
            self.changeWhiteBalance(2.0, 1.0, 2.0, "WhiteFluro") # ~WhiteFluro
        elif k=='2':
            self.changeWhiteBalance(2.0, 1.0, 1.5, "Daylight") # ~Daylight
        elif k=='3':
            self.changeWhiteBalance(2.5, 1.0, 1.5, "Cloudy.") # ~Cloudy
        elif k=='4':
            self.changeWhiteBalance(1.5, 1.0, 2.0, "Tungsten") # ~Tungsten
        elif k=='0':
            self.changeWhiteBalance(1.0, 1.0, 1.0, "Passthrough") # =passthrough

        elif k=='q' or k=='Q':
            self.toggleQuality()
        elif k=='a' or k=='A':
            self.toggleAnamorphic()
        elif k=='e' or k=='E':
            self.toggleEncoding()

        else:
            super(Viewer,self).key(k,x,y)
    def specialkey(self,k,x,y):
        #print "special key",k
        if k==100: # Left cursor
            self.jump(-self._fps) # Go back 1 second (will wrap)
        elif k==102: # Right cursor
            self.jump(self._fps) # Go forward 1 second (will wrap)
        elif k==101: # Up cursor
            self.scaleBrightness(1.1)
        elif k==103: # Down cursor
            self.scaleBrightness(1.0/1.1)
        else:
            super(Viewer,self).specialkey(k,x,y)
    def scaleBrightness(self,scale):
        self.setting_brightness *= scale
        self.refresh()
    def changeWhiteBalance(self, R, G, B, Name="WB"):
        self.setting_rgb = (R, G, B)
        print "%s:\t %.1f %.1f %.1f"%(Name, R, G, B)
        self.refresh()
    def toggleQuality(self):
        self.setting_highQuality = not self.setting_highQuality
    def toggleAnamorphic(self):
        self.anamorphic = not self.anamorphic
    def onIdle(self):
        if self.needsRefresh and self.paused:
            self.redisplay()
        elif self.paused:
            time.sleep(0.016) # Sleep for one frame

        now = GLCompute.timeInUsec()
        if not self.needsRefresh and not self.paused and (now-self._last >= (1.0/self._fps)):
            #print now,self._last,1.0/self._fps
            self.redisplay()

        self.needsRefresh = False

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
            kwargs = {"stdin":subprocess.PIPE,"stdout":subprocess.PIPE,"stderr":subprocess.STDOUT}
            if subprocess.mswindows:
                su = subprocess.STARTUPINFO() 
                su.dwFlags |= subprocess.STARTF_USESHOWWINDOW 
                su.wShowWindow = subprocess.SW_HIDE 
                kwargs["startupinfo"] = su
            args = [exe,"-f","rawvideo","-pix_fmt","rgb48","-s","%dx%d"%(self._raw.width(),self._raw.height()),"-r","%d"%self._fps,"-i","-","-an","-f","mov","-vf","vflip","-vcodec","prores_ks","-profile:v","3","-r","%d"%self._fps,self.outfilename]
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

    # Encoder interface to demosaicing -> frames are returned to here if encoding setting is True
    def demosaicDuration(self, duration):
        # Maintain an average measure of how long it takes this machine to CPU demosaic
        self.demosaicCount += 1
        self.demosaicTotal += duration
        self.demosaicAverage = self.demosaicTotal/float(self.demosaicCount)
        print "demosaicAverage:",self.demosaicAverage
    def encode(self, index, frame):
        if self.setting_encoding and self.encoderProcess and self.lastEncodedFrame:
            if index < self.lastEncodedFrame:
                self.toggleEncoding() # Stop encoding as we reached the end
                self.paused = True
                self.jump(-1) # Should go back to last frame
                self.refresh()
                return        
        if self.encoderProcess:
            #print "Encoding frame:",index
            self.encoderProcess.stdin.write(frame.tostring())
        self.lastEncodedFrame = index

def main():
    filename = sys.argv[1]
    if len(sys.argv)>2:
        outfilename = sys.argv[2]
    else:
        # Try to pick a sensible default filename for any possible encoding
        outfilename = sys.argv[1]+".MOV"

    try:
        r = MlRaw.loadRAWorMLV(filename)
    except Exception, err:
        sys.stderr.write('Could not open file %s. Error:%s\n'%(filename,str(err)))
        return 1
    rmc = Viewer(r,outfilename)
    return rmc.run()
    return 0

def launchFromGui(rawfile,outfilename=None):
    rmc = Viewer(rawfile,outfilename)
    return rmc.run()
    
if __name__ == '__main__':
    sys.exit(main())
