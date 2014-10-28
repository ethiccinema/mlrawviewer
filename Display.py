"""
Display.py, part of MlRawViewer
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
from ShaderGraph import *
from ShaderDisplaySimple import *
from ShaderText import *

programpath = os.path.abspath(os.path.split(sys.argv[0])[0])

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

class Graph(ui.Button):
    def __init__(self,**kwds):
        super(Graph,self).__init__(**kwds)
        self.shader = ShaderGraph()
    def render(self,scene,matrix,opacity):
        PLOG(PLOG_CPU,"Geometry render %d,%d"%self.pos)
        self.updateMatrix()
        m = self.matrix.copy()
        m.mult(matrix);
        finalopacity = self.opacity * opacity
        if finalopacity>0.0:
            PLOG(PLOG_CPU,"Geometry render draw %d,%d"%self.pos)
            if self.clip:
                glEnable(GL_STENCIL_TEST)
                glStencilFunc(GL_ALWAYS, 1, 0xFF);
                glStencilOp(GL_KEEP, GL_KEEP, GL_REPLACE);
                glStencilMask(0xFF);
            self.shader.draw(m,128,128,self.texture,finalopacity)
            PLOG(PLOG_CPU,"Geometry render children %d,%d"%self.pos)
        if self.clip:
            glStencilFunc(GL_EQUAL, 1, 0xFF)
            glStencilMask(0x00);
        for c in self.children:
            c.render(scene,m,finalopacity) # Relative to parent
        if self.clip:
            glDisable(GL_STENCIL_TEST)
            glStencilMask(0xFF);
        PLOG(PLOG_CPU,"Geometry render done %d,%d"%self.pos)
class DisplayScene(ui.Scene):
    def __init__(self,frames,**kwds):
        super(DisplayScene,self).__init__(**kwds)
        self.dropperActive = False
        self.frames = frames # Frames interface
        self.icons = self.frames.icons
        self.iconsz = self.frames.iconsz
        self.icontex = self.frames.icontex
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
        self.mapping = self.newIcon(0,90,128,128,11,self.mappingClick,"Curve: sRGB,R709,Linear,LOG,HDR,S-Log,S-Log2,Log-C,C-Log (Key:T)")
        self.mapping.colour = (0.5,0.5,0.5,0.5) # Quite transparent white
        self.mapping.setScale(0.25)
        self.update = self.newIcon(0,0,128,128,30,self.updateClick,"New version of MlRawViewer is available. Click to download")
        self.update.colour = (0.5,0.1,0.0,0.5)
        self.update.setScale(0.5)
        self.loop = self.newIcon(0,0,128,128,31,self.loopClick,"Loop clip or play once (Key:L)")
        self.loop.colour = (0.5,0.5,0.5,0.5)
        self.loop.setScale(0.5)
        self.outformat = self.newIcon(0,0,128,128,20,self.outfmtClick,"Export format - MOV or DNG (Key:D)")
        self.outformat.colour = (0.5,0.5,0.5,0.5)
        self.outformat.setScale(0.5)
        self.addencode = self.newIcon(0,0,128,128,33,self.addEncodeClick,"Add clip to export queue (Key:E)")
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
        self.mdbg = ui.Button(0,0,self.browserClick,svbo=frames.svbo,onhover=self.updateTooltip,onhoverobj="File info. Click to change (Key:BACKSPACE)")
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
        self.histogram = Graph(width=128,height=128,onclick=self.histogramClick,svbo=self.frames.svbo)
        self.iconItems = [self.fullscreen,self.mapping,self.drop,self.quality,self.stripes,self.loop,self.outformat,self.addencode,self.play]
        self.overlay = [self.iconBackground,self.progressBackground,self.progress,self.timestamp,self.update,self.balance,self.balanceHandle,self.brightness,self.brightnessHandle,self.mark,self.mdbg,self.metadata,self.exportq,self.coldata,self.ttbg,self.tooltip,self.histogram]
        self.overlay.extend(self.iconItems)
        self.overlay.extend(self.ciItems)
        self.overlay.append(self.whitePicker) # So it is on the bottom
        self.drawables.extend([self.display])
        self.drawables.extend(self.overlay)
        self.timeline = ui.Timeline()
        self.fadeAnimation = ui.Animation(self.timeline,1.0)
        self.clearhover = self.clearTooltip
        self.wasFull = None
        self.refreshCursor = False

    def clearTooltip(self):
        if self.tooltip.text != "":
            self.tooltip.text = ""
            if self.frames.paused:
                self.frames.refresh()

    def updateTooltip(self,button,tiptext):
        if tiptext != self.tooltip.text:
            self.tooltip.text = tiptext
            if self.frames.paused:
                self.frames.refresh()

    def isDirty(self):
        dirty = False
        for d in self.drawables:
            if d.matrixDirty: dirty = True
        return dirty

    def setRgbImage(self,rgbImage):
        self.display.setRgbImage(rgbImage)
    def setHistogram(self,histogram):
        self.histogram.texture = histogram

    def browserClick(self,x,y):
        self.frames.toggleBrowser()

    def histogramClick(self,x,y):
        self.frames.changeHistogram()

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
        s = os.path.split(r.filename)[1]+"\n"
        s += r.make()+" "+r.model()
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
        if self.frames.setting_tonemap==0:
            s += "\nCurve: Linear"
        elif self.frames.setting_tonemap==1:
            s += "\nCurve: HDR global tone map"
        elif self.frames.setting_tonemap==2:
            s += "\nCurve: Log 8"
        elif self.frames.setting_tonemap==3:
            s += "\nCurve: sRGB"
        elif self.frames.setting_tonemap==4:
            s += "\nCurve: Rec.709"
        elif self.frames.setting_tonemap==5:
            s += "\nCurve: S-Log"
        elif self.frames.setting_tonemap==6:
            s += "\nCurve: S-Log2"
        elif self.frames.setting_tonemap==7:
            s += "\nCurve: Log-C"
        elif self.frames.setting_tonemap==8:
            s += "\nCurve: C-Log"
        if self.frames.setting_lut1d1 != None:
            s += "\n1D LUT1:%s"%self.frames.setting_lut1d1.name()
        if self.frames.setting_lut3d != None:
            s += "\n3D LUT :%s"%self.frames.setting_lut3d.name()
        if self.frames.setting_lut1d2 != None:
            s += "\n1D LUT2:%s"%self.frames.setting_lut1d2.name()
        return s
        #make = self.frames.raw.
        #self.frames.playFrame.

    def prepareToRender(self):
        """
        f = self.frame
        frameNumber = int(f % self.raw.frames())
        """
        self.display.displayShader.prepare(self.frames.svbo)
        self.histogram.shader.prepare(self.frames.svbo,self.histogram.size[0],self.histogram.size[1])
        self.timeline.setNow(time.time())
        idle = self.frames.userIdleTime()
        if idle>5.0 and self.fadeAnimation.targval == 1.0 and not self.frames.encoding() or self.refreshCursor:
            if not self.frames.hideOverlay:
                self.fadeAnimation.setTarget(0.0,2.0,0.0,ui.Animation.SMOOTH)
            else:
                self.fadeAnimation.setTarget(0.0,0.0,0.0,ui.Animation.SMOOTH)
                self.frames.refresh()
            self.frames.setCursorVisible(False)
        elif idle<=5.0 and self.fadeAnimation.targval == 0.0 or self.refreshCursor:
            self.frames.setCursorVisible(True)
            self.fadeAnimation.setTarget(1.0,0.5,0.0,ui.Animation.SMOOTH)
        self.refreshCursor = False
        if self.frames._isFull != self.wasFull: # work around for GLFW bug
            self.refreshCursor = True
            self.wasFull = self.frames._isFull
            self.frames.refresh()
        self.overlayOpacity = self.fadeAnimation.value()
        if self.frames.paused and not self.frames.hideOverlay: self.overlayOpacity = 1.0
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
        self.histogram.shader.type = self.frames.setting_histogram
        self.histogram.setPos(btl,btr-160.)
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
        self.mdbg.size = (self.metadata.size[0]+24.0,self.metadata.size[1]+12.0)
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


