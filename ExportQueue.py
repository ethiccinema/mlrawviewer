"""
ExportQueue.py
(c) Andrew Baldwin 2014

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

import sys,os,threading,Queue,time,math,subprocess,multiprocessing,wave

import wavext

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

import MlRaw,DNG

import GLCompute
import GLComputeUI as ui
from ShaderDemosaicCPU import *
from ShaderPreprocess import *
from ShaderPatternNoise import *

import numpy as np

import bitunpack

def at(entries,tag,val):
    entries.append((tag[0],tag[1][0],1,(val,)))
def atm(entries,tag,val):
    entries.append((tag[0],tag[1][0],len(val),val))

class ExportQueue(threading.Thread):
    """
    Process a queue of export jobs one at a time but as quickly as possible
    Could be any kind of export in future - DNG, LinearDNG (demosacing), ProRes encode...
    """
    COMMAND_ADD_JOB = 0
    COMMAND_REMOVE_JOB = 1
    COMMAND_REMOVE_ALL_JOBS = 2
    COMMAND_PAUSE = 3
    COMMAND_PROCESS = 4
    COMMAND_END = 5
    JOB_DNG = 0
    JOB_MOV = 1
    JOB_MKV = 2
    PREPROCESS_NONE = 0
    PREPROCESS_ALL = 1
    def __init__(self,config,**kwds):
        super(ExportQueue,self).__init__(**kwds)
        self.config = config
        self.iq = Queue.Queue()
        self.bgiq = Queue.Queue()
        self.wq = Queue.Queue()
        self.dq = Queue.Queue()
        self.tc = Queue.Queue()
        self.jobs = {}
        self.jobstatus = {}
        self.jobindex = 0
        self.currentjob = -1
        self.cancel = False
        self.endflag = False
        self.ended = False
        self.busy = False
        self.daemon = True
        self.needBgDraw = False
        self.shaderQuality = None
        self.rgbUploadTex = None
        self.shaderPatternNoise = None
        self.shaderPreprocess = None
        self.luttex = None
        self.currentLut = None
        self.luttex1d1 = None
        self.currentLut1d1 = None
        self.luttex1d2 = None
        self.currentLut1d2 = None
        self.rgbImage = None
        self.svbo = None
        self.pauseState = True
        self.context = GLCompute.ContextState()
        self.start()
    def pause(self):
        self.iq.put((self.COMMAND_PAUSE,))
    def process(self):
        self.iq.put((self.COMMAND_PROCESS,))
    def processCommands(self,block):
        once = True
        #print "processCommand",self.iq.empty()
        while self.pauseState or once or not self.iq.empty():
            if block or self.pauseState:
                command = self.iq.get()
            else:
                try:
                    command = self.iq.get_nowait()
                except Queue.Empty:
                    return # Nothing to do

            # Process the command
            ct = command[0]
            if ct==self.COMMAND_ADD_JOB:
                job = command[1]
                ix = job[0]
                self.jobs[ix] = job
                self.jobstatus[ix] = 0.0
                #print "added job",ix
            elif ct==self.COMMAND_REMOVE_JOB:
                ix = command[1]
                #print "removing job",ix
                if self.currentjob == ix:
                    self.cancel = True # Terminate early
                else:
                    if ix in self.jobs:
                        del self.jobs[ix]
                        del self.jobstatus[ix]
            elif ct==self.COMMAND_REMOVE_ALL_JOBS:
                self.cancel = True
                remove = []
                for k in self.jobs.keys():
                    if k!=self.currentjob:
                        remove.append(k)
                for k in remove:
                    try:
                        del self.jobs[k]
                        del self.jobstatus[k]
                    except:
                        pass
                #print "removed all jobs"
            elif ct==self.COMMAND_PAUSE:
                self.pauseState = True
            elif ct==self.COMMAND_PROCESS:
                self.pauseState = False
            elif ct==self.COMMAND_END:
                self.endflag = True
            once = False
            self.iq.task_done()

    def cancelJob(self,ix):
        #print "requesting cancel of",ix
        self.iq.put((self.COMMAND_REMOVE_JOB,ix))
    def cancelAllJobs(self):
        #print "requesting cancel of all"
        self.iq.put((self.COMMAND_REMOVE_ALL_JOBS,))
    def end(self):
        self.iq.put((self.COMMAND_END,))
    def hasEnded(self):
        return self.ended
    def waitForEnd(self):
        self.join()
    # Job status
    def status(self,index):
        if index >= self.jobindex:
            return 0.0
        elif index in self.jobstatus:
            return self.jobstatus[index]
        else:
            return 1.0
    # Queue Job calls
    def exportDng(self,rawfile,dngdir,wavfile,startFrame=0,endFrame=None,audioOffset=0.0,bits=16,rgbl=None,preprocess=0):
        return self.submitJob(self.JOB_DNG,rawfile,dngdir,wavfile,startFrame,endFrame,audioOffset,bits,rgbl,preprocess)
    def exportMov(self,rawfile,movfile,wavfile,startFrame=0,endFrame=None,audioOffset=0.0,rgbl=None,tm=None,matrix=None,preprocess=0):
        return self.submitJob(self.JOB_MOV,rawfile,movfile,wavfile,startFrame,endFrame,audioOffset,rgbl,tm,matrix,preprocess)
    def exportMkv(self,rawfile,movfile,wavfile,startFrame=0,endFrame=None,audioOffset=0.0,rgbl=None,tm=None,matrix=None,preprocess=0):
        return self.submitJob(self.JOB_MKV,rawfile,movfile,wavfile,startFrame,endFrame,audioOffset,rgbl,tm,matrix,preprocess)
    def submitJob(self,*args):
        ix = self.jobindex
        self.jobindex += 1
        job = tuple([ix]+list(args))
        self.iq.put((self.COMMAND_ADD_JOB,job))
        return ix
    def run(self):
        try:
            while 1: # Wait for the next job in the Queue
                if self.endflag:
                    break
                self.processCommands(block=(len(self.jobs)==0))
                if len(self.jobs)>0:
                    # There is something to do
                    pendingJobs = self.jobs.keys()
                    pendingJobs.sort()
                    self.currentjob = pendingJobs[0]
                    self.busy = True
                    self.cancel = False
                    try:
                        self.nextJob(self.jobs[self.currentjob])
                    except:
                        print "Export job failed:"
                        import traceback
                        traceback.print_exc()
                    if self.currentjob in self.jobs:
                        del self.jobs[self.currentjob]
                        del self.jobstatus[self.currentjob]
                    self.currentjob = -1
                    self.cancel = False
                    if len(self.jobs)==0:
                        self.busy = False
        except:
            pass
        self.ended = True

    def nextJob(self,job):
        # Runs on processing thread
        jobType = job[1]
        jobArgs = job[2:]
        if jobType == self.JOB_DNG:
            self.doExportDng(job[0],jobArgs)
        elif jobType == self.JOB_MOV:
            self.doExportMov(job[0],jobArgs)
        elif jobType == self.JOB_MKV:
            self.doExportMkv(job[0],jobArgs)
        else:
            pass

    def fpsParts(self,r):
        fps = r.fps
        fpsnum = r.fpsnum
        fpsden = r.fpsden
        fpsover = r.getMeta("fpsOverride_v1")
        if fpsover != None:
            #print "fpsover",fpsover
            if fpsover == 24000.0/1001.0:
                fpsnum,fpsden = 24000,1001
            elif fpsover == 24000.0/1000.0:
                fpsnum,fpsden = 24000,1000
            elif fpsover == 25000.0/1000.0:
                fpsnum,fpsden = 25000,1000
            elif fpsover == 30000.0/1001.0:
                fpsnum,fpsden = 30000,1001
            elif fpsover == 30000.0/1000.0:
                fpsnum,fpsden = 30000,1000
            elif fpsover == 48000.0/1000.0:
                fpsnum,fpsden = 48000,1000
            elif fpsover == 50000.0/1000.0:
                fpsnum,fpsden = 50000,1000
            elif fpsover == 60000.0/1000.0:
                fpsnum,fpsden = 60000,1000
            if fpsover != None:
                fps = fpsover
        #print "FPS parts:",fps,fpsnum,fpsden
        return fps,fpsnum,fpsden

    def setDngHeader(self,r,d,bits,frame,rgbl,ljpeg=False,date=None):
        d.stripTotal = 3000000
        d.bo = "<" # Little endian
        # Prepopulate DNG with basic set of tags for a single image
        ifd = DNG.DNG.IFD(d)
        d.ifds.append(ifd)
        d.FULL_IFD = ifd
        ifd.subFileType = 0 # Full
        ifd.width = r.width()
        ifd.length = r.height()
        e = ifd.entries
        at(e,DNG.Tag.NewSubfileType,0)
        at(e,DNG.Tag.ImageWidth,r.width())
        at(e,DNG.Tag.ImageLength,r.height())
        at(e,DNG.Tag.BitsPerSample,bits)
        ifd.BitsPerSample = (bits,)
        if ljpeg:
            at(e,DNG.Tag.Compression,7) # LJPEG
        else:
            at(e,DNG.Tag.Compression,1) # No compression
        at(e,DNG.Tag.PhotometricInterpretation,32803) # CFA
        at(e,DNG.Tag.FillOrder,1)
        atm(e,DNG.Tag.Make,r.make()+"\0")
        atm(e,DNG.Tag.Model,r.make()+" "+r.model()+"\0")
        if not ljpeg:
            at(e,DNG.Tag.StripOffsets,0)
        at(e,DNG.Tag.Orientation,1)
        at(e,DNG.Tag.SamplesPerPixel,1)
        if not ljpeg:
            at(e,DNG.Tag.RowsPerStrip,r.height())
            ifd.RowsPerStrip = r.height()
            at(e,DNG.Tag.StripByteCounts,0)
        at(e,DNG.Tag.PlanarConfiguration,1) # Chunky
        atm(e,DNG.Tag.Software,"MlRawViewer"+"\0")
        if frame.rtc != None:
            se,mi,ho,da,mo,ye = frame.rtc[1:7]
            atm(e,DNG.Tag.DateTime,"%04d:%02d:%02d %02d:%02d:%02d\0"%(ye+1900,mo,da,ho,mi,se))
        #atm(e,DNG.Tag.DateTime,"1988:10:01 23:23:23")
        if ljpeg:
            at(e,DNG.Tag.TileWidth,r.width()/2)
            at(e,DNG.Tag.TileLength,r.height())
            ifd.TileWidth = r.width()/2
            atm(e,DNG.Tag.TileOffsets,(0,0))
            atm(e,DNG.Tag.TileByteCounts,(0,0))
        atm(e,DNG.Tag.CFARepeatPatternDim,(2,2)) # No compression
        atm(e,DNG.Tag.CFAPattern,(0,1,1,2)) # No compression
        at(e,DNG.Tag.EXIF_IFD,0)
        atm(e,DNG.Tag.DNGVersion,(1,4,0,0))
        atm(e,DNG.Tag.UniqueCameraModel,r.make()+" "+r.model()+"\0")
        atm(e,DNG.Tag.LinearizationTable,[i for i in range(2**14-1)])
        at(e,DNG.Tag.BlackLevel,r.black)
        at(e,DNG.Tag.WhiteLevel,r.white)
        m = [(int(v*10000),10000) for v in r.colorMatrix.A1]
        atm(e,DNG.Tag.ColorMatrix1,m)
        aa = r.activeArea
        fw = r.width()
        fh = r.height()
        tlx,tly = aa[1],aa[0]
        aw = aa[3]-aa[1]
        ah = aa[2]-aa[0]
        cw,ch = r.cropSize
        if aw>=fw:
            aw = fw
            tlx = 0
            cw = fw
        if ah>=fh:
            ah = fh
            tly = 0
            ch = fh
        area = (tly,tlx,tly+ah,tlx+aw)
        atm(e,DNG.Tag.DefaultCropOrigin,r.cropOrigin)
        atm(e,DNG.Tag.DefaultCropSize,(cw,ch))
        if rgbl==None: # Pick a default
            atm(e,DNG.Tag.AsShotNeutral,((473635,1000000),(1000000,1000000),(624000,1000000)))
            atm(e,DNG.Tag.CameraSerialNumber,r.bodySerialNumber()+"\0")
            atm(e,DNG.Tag.ActiveArea,area)
        else:
            asnred = int(1000000/rgbl[0])
            asngreen = int(1000000/rgbl[1])
            asnblue = int(1000000/rgbl[2])
            atm(e,DNG.Tag.AsShotNeutral,((asnred,1000000),(asngreen,1000000),(asnblue,1000000)))
            ev = int(1000000*math.log(rgbl[3],2.0))
            at(e,DNG.Tag.BaselineExposure,(0,1000000)) # Not yet used by dcraw-based tools :-(
            atm(e,DNG.Tag.CameraSerialNumber,r.bodySerialNumber()+"\0")
            atm(e,DNG.Tag.ActiveArea,area)
            at(e,DNG.Tag.BaselineExposureOffset,(ev,1000000)) # Not yet used by dcraw-based tools :-(
        fps,fpsnum,fpsden = self.fpsParts(r)
        if date != None:
            se,mi,ho,da,mo,ye = date
            atm(e,DNG.Tag.TimeCodes,[0,se%10|(se/10)<<4,mi%10|(mi/10)<<4,ho%10|(ho/10)<<4,0,0,0,0])
        else:
            atm(e,DNG.Tag.TimeCodes,[0,0,0,0,0,0,0,0])
        at(e,DNG.Tag.FrameRate,(fpsnum,fpsden))
        exif = DNG.DNG.IFD(d)
        d.ifds[0].EXIF_IFD = exif
        e = exif.entries
        if frame.expo != None:
            expusec = frame.expo[-1]
            tv = -math.log(expusec/1000000.0,2.0)*1024.0
            at(e,DNG.Tag.ExposureTime,(expusec,1000000))
            if frame.lens != None:
                at(e,DNG.Tag.FNumber,(frame.lens[2][3],100))
            at(e,DNG.Tag.PhotographicSensitivity,frame.expo[2])
            at(e,DNG.Tag.SensitivityType,3) # ISO
            at(e,DNG.Tag.ShutterSpeedValue,(int(tv),1024))
        if frame.lens != None:
            dist = frame.lens[2][2]
            if dist == 65535:
                dist = 0xFFFFFFFF
            at(e,DNG.Tag.SubjectDistance,(dist,1))
            at(e,DNG.Tag.FocalLength,(frame.lens[2][1],1))
            at(e,DNG.Tag.FocalLengthIn35mmFilm,frame.lens[2][1])
            atm(e,DNG.Tag.EXIFPhotoBodySerialNumber,r.bodySerialNumber()+"\0")
            atm(e,DNG.Tag.EXIFPhotoLensModel,frame.lens[0]+"\0")

        atm(e,DNG.Tag.ExifVersion,"0230") # 0230
        if frame.rtc != None:
            se,mi,ho,da,mo,ye = frame.rtc[1:7]
            atm(e,DNG.Tag.DateTimeOriginal,"%04d:%02d:%02d %02d:%02d:%02d\0"%(ye+1900,mo,da,ho,mi,se))

    def tempEncoderWav(self,wavfile,fps,tempname,inframe,outframe,audioOffset,dt=None,sn=""):
        wav = wave.open(wavfile,'r')
        tempwav = wavext.wavext(tempname)
        tempwav.setparams(wav.getparams())
        if dt!=None:
            se,mi,ho,da,mo,ye = dt
            od = "%04d:%02d:%02d"%(ye+1900,mo,da)
            ot = "%02d:%02d:%02d"%(ho,mi,se)
            bext = wavext.bext(originatorReference=sn,originationDate=od,originationTime=ot)
        else:
            bext = wavext.bext()
        tempwav.setextra((bext,wavext.ixml()))
        channels,width,framerate,nframe,comptype,compname = wav.getparams()
        frameCount = int(framerate * float(outframe-inframe+1)/float(fps))
        startFrame = int((audioOffset+(float(inframe)/float(fps)))*framerate)
        padframes = 0
        readPos = startFrame
        if startFrame<0:
            padframes = -startFrame
            readPos = 0
        wav.setpos(readPos)
        if (startFrame+frameCount)>=(nframe):
            frames = wav.readframes(nframe-startFrame) # Less than all
        else:
            frames = wav.readframes(frameCount) # All
        if padframes>0:
            pad = "\0"*padframes*channels*width
            tempwav.writeframes(pad)
        tempwav.writeframes(frames)
        tempwav.close()
        wav.close()

    def doExportDng(self,jobindex,args):
        filename,dngdir,wavfile,startFrame,endFrame,audioOffset,bits,rgbl,preprocess= args
        if preprocess:
            self.needBgDraw = True
        try:
            self.processExportDng(jobindex,args)
        except:
            import traceback
            traceback.print_exc()
            pass
        # Clean up
        if preprocess:
            self.needBgDraw = False

    def wavOverride(self,r,wavname):
        newwavname = r.getMeta("wavfile_v1")
        if newwavname != None: wavname = newwavname
        return wavname

    def rgblOverride(self,raw,rgbl,tm=None):
        r,g,b = rgbl[:3]
        l = rgbl[3]
        newl = raw.getMeta("brightness_v1")
        if newl != None: l = newl
        newrgb = raw.getMeta("balance_v1")
        if newrgb != None: r,g,b = newrgb
        newtm = raw.getMeta("tonemap_v1")
        if newtm != None: tm = newtm
        return (r,g,b,l),tm

    def processExportDng(self,jobindex,args):
        filename,dngdir,wavfile,startFrame,endFrame,audioOffset,bits,rgbl,preprocess= args
        os.mkdir(dngdir)
        target = dngdir
        r = MlRaw.loadRAWorMLV(filename)
        if endFrame == None:
            endFrame = r.frames()-1
        todo = endFrame-startFrame+1
        if r.audioFrames()>0:
            # Must index the whole file in order that we have the wav file
            while r.indexingStatus()<1.0:
                time.sleep(0.1)
        fps,fpsnum,fpsden = self.fpsParts(r)
        rgbl,dummy = self.rgblOverride(r,rgbl)
        wavfile = self.wavOverride(r,wavfile)
        if wavfile != None:
            wavfile = os.path.join(os.path.split(filename)[0],wavfile)
        targfile = os.path.splitext(os.path.split(r.filename)[1])[0]
        target = os.path.join(target,targfile)
        print "DNG export to",repr(target),"started"
        self.tileCompressor = threading.Thread(target=self.tileCompress)
        self.tileCompressor.daemon = True
        self.tileCompressor.start()
        self.writer = threading.Thread(target=self.dngWriter)
        self.writer.daemon = True
        self.writer.start()
        self.writtenFrame = 0
        r.preloadFrame(startFrame)
        r.preloadFrame(startFrame+1) # Preload one ahead
        ljpeg = True
        if bits == 14: jpeg = False
        wavneeded = False
        if wavfile != None:
            if os.path.exists(wavfile):
                wavneeded = True
        wavmade = False
        for i in range(endFrame-startFrame+1):
            self.processCommands(block=False)
            f = r.frame(startFrame+i)
            f.writeljpeg = ljpeg
            d = DNG.DNG()

            if f.rtc != None:
                date = f.rtc[1:7]
            else:
                date = (0,0,0,0,0,0)
            if wavneeded and not wavmade:
                rhead = os.path.splitext(os.path.split(filename)[1])[0]
                outwavname = os.path.join(dngdir, rhead + ".WAV")
                self.tempEncoderWav(wavfile,fps,outwavname,startFrame,endFrame,audioOffset,date,r.bodySerialNumber())
                wavmade = True
            self.setDngHeader(r,d,bits,f,rgbl,ljpeg,date)
            ifd = d.FULL_IFD
            if ((startFrame+i+1)<r.frames()):
                r.preloadFrame(startFrame+i+1)
            while self.writtenFrame<(i-10):
                # Give writing thread time to write...
                if self.endflag or self.cancel:
                    break
                time.sleep(0.1)
            if preprocess==self.PREPROCESS_ALL:
                # Must first preprocess with shader
                self.bgiq.put((f,d,2,r.width(),r.height(),i,target,rgbl))
            else:
                d.ljpeg = ljpeg
                if bits==14:
                    d.rawdata = np.frombuffer(f.rawdata,dtype=np.uint16).byteswap().tostring()
                elif bits==16:
                    f.convert() # Will block if still processing
                    d.rawdata = np.frombuffer(f.rawimage,dtype=np.uint16).tostring()
                self.wq.put((i,target,d)) # Queue writing
            st = float(self.writtenFrame+1)/float(todo)
            #print "%.02f%%"%(st*100.0)
            self.jobstatus[jobindex] = st
            if self.endflag or self.cancel:
                break
        if preprocess==self.PREPROCESS_ALL:
                # Must first preprocess with shader
            self.bgiq.put(None)
        else:
            self.wq.put(None) # Finish
        while (self.writtenFrame+1)<todo:
            time.sleep(0.5)
            st = float(self.writtenFrame+1)/float(todo)
            #print "%.02f%%"%(st*100.0)
            self.jobstatus[jobindex] = st
            if self.endflag or self.cancel:
                break
        self.wq.join()
        self.writer.join()
        self.jobstatus[jobindex] = 1.0
        print "DNG export to",repr(target),"finished"
        r.close()

    def tileCompress(self):
        tilejob = self.tc.get()
        while tilejob != None:
            try:
                rawdata,w,l = tilejob
                self.nextCompressedTile = bitunpack.pack16tolj(rawdata,w,l/2,16,w,w/2,w/2,"")
                self.tc.task_done()
            except:
                import traceback
                traceback.print_exc()
                self.nextCompressedTile = None
            tilejob = self.tc.get()

    def dngWriter(self):
        nextbuf = self.wq.get()
        while nextbuf != None:
            try:
                index,target,dng = nextbuf
                ifd = dng.FULL_IFD
                if dng.ljpeg:
                    self.tc.put((dng.rawdata,ifd.width,ifd.length))
                    tile1 = bitunpack.pack16tolj(dng.rawdata,ifd.width,ifd.length/2,16,0,ifd.width/2,ifd.width/2,"")
                    #tile2 = bitunpack.pack16tolj(dng.rawdata,ifd.width,ifd.length/2,16,ifd.width,ifd.width/2,ifd.width/2,"")
                    self.tc.join() # Wait for it to be done
                    tile2 = self.nextCompressedTile
                    ifd._tiles = [
                        tile1,
                        tile2
                        ]
                else:
                    ifd._strips = [ dng.rawdata ]
                dng.writeFile(target+"_%06d.dng"%index)
                self.writtenFrame = index
            except:
                import traceback
                traceback.print_exc()
                self.cancel = True
            self.wq.task_done()
            time.sleep(0.016) # Yield
            nextbuf = self.wq.get()
        self.wq.task_done()
        #print "WRITER FINISHED!"


    def doExportMov(self,jobindex,args):
        self.needBgDraw = True
        filename,movfile,wavfile,startFrame,endFrame,audioOffset,rgbl,tm,matrix,preprocess = args
        try:
            rotateConfig = "-vf vflip " 
            
            # Raw picture is upside down. Only rotate if rotate is not required
            if self.config.getState("rotate"):
                rotateConfig = "-vf hflip "
                
            videoConfig = rotateConfig + "-f mov -vcodec prores_ks -profile:v 4 -alpha_bits 0 -vendor ap4h -q:v 0"
            audioConfig = "-acodec copy"
            extension = "MOV"
            self.processExportFFMpeg(jobindex,extension,videoConfig,audioConfig,filename,movfile,wavfile,startFrame,endFrame,audioOffset,rgbl,tm,matrix,preprocess)
        except:
            import traceback
            traceback.print_exc()
            pass
        # Clean up
        self.needBgDraw = False
        if self.encoderProcess:
            self.encoderProcess.stdin.close()
            self.encoderProcess.wait()
            self.encoderProcess = None
        tempwavfile = movfile[:-4] + ".WAV"
        if os.path.exists(tempwavfile):
            os.remove(tempwavfile)
        self.encoderOutput = None  
        self.stdoutReader = None
        
    def doExportMkv(self,jobindex,args):
        self.needBgDraw = True
        filename,movfile,wavfile,startFrame,endFrame,audioOffset,rgbl,tm,matrix,preprocess = args
        try:
            rotateConfig = "-vf vflip " 
            
            # Raw picture is upside down. Only rotate if rotate is not required
            if self.config.getState("rotate"):
                rotateConfig = "-vf hflip "
                
            videoConfig = rotateConfig + "-vcodec huffyuv"
            audioConfig = "-acodec flac"
            extension = "mkv"
            self.processExportFFMpeg(jobindex,extension,videoConfig,audioConfig,filename,movfile,wavfile,startFrame,endFrame,audioOffset,rgbl,tm,matrix,preprocess)
        except:
            import traceback
            traceback.print_exc()
            pass
        # Clean up
        self.needBgDraw = False
        if self.encoderProcess:
            self.encoderProcess.stdin.close()
            self.encoderProcess.wait()
            self.encoderProcess = None
        tempwavfile = movfile[:-4] + ".WAV"
        if os.path.exists(tempwavfile):
            os.remove(tempwavfile)
        self.encoderOutput = None
        self.stdoutReader = None

    def processExportFFMpeg(self,jobindex,extension,videoConfig,audioConfig,filename,movfile,wavfile,startFrame,endFrame,audioOffset,rgbl,tm,matrix,preprocess):
        import codecs
        toUtf8 = codecs.getencoder('UTF8')
        target = movfile
        print extension,"export to",repr(movfile),"started"
        tempwavname = None
        r = MlRaw.loadRAWorMLV(filename)
        if endFrame == None:
            endFrame = r.frames()-1
        todo = endFrame-startFrame+1
        if r.audioFrames()>0:
            # Must index the whole file in order that we have the wav file
            while r.indexingStatus()<1.0:
                time.sleep(0.1)
        fps,fpsnum,fpsden = self.fpsParts(r)
        rgbl,tm = self.rgblOverride(r,rgbl,tm)
        lut1d1 = r.getMeta("lut1d1_v1")
        if lut1d1 != None:
            print "Exporting using 1D LUT1",lut1d1.name()
        lut = r.getMeta("lut3d_v1")
        if type(lut)==tuple:
            lut = None
        if lut != None:
            print "Exporting using 3D LUT",lut.name()
        lut1d2 = r.getMeta("lut1d2_v1")
        if lut1d2 != None:
            print "Exporting using 1D LUT2",lut1d2.name()
        wavfile = self.wavOverride(r,wavfile)
        if wavfile != None:
            wavfile = os.path.join(os.path.split(filename)[0],wavfile)
            if os.path.exists(wavfile):
                tempwavname = movfile[:-4] + ".WAV"
                self.tempEncoderWav(wavfile,fps,tempwavname,startFrame,endFrame,audioOffset)
        fw = r.width()
        fh = r.height()
        aa = r.activeArea
        tlx,tly = aa[1],aa[0]
        aw = aa[3]-aa[1]
        ah = aa[2]-aa[0]
        if aw>=fw:
            aw = fw
            tlx = 0
        if ah>=fh:
            ah = fh
            tly = 0
        area = (tlx,tly,aw,ah)
        if subprocess.mswindows:
            exe = "ffmpeg.exe"
        else:
            exe = "ffmpeg"
        programpath = os.path.abspath(os.path.split(sys.argv[0])[0])
        if getattr(sys,'frozen',False):
            programpath = sys._MEIPASS
        localexe = os.path.join(programpath,exe)
        #print localexe
        if os.path.exists(localexe):
            exe = localexe
        kwargs = {"stdin":subprocess.PIPE,"stdout":subprocess.PIPE,"stderr":subprocess.STDOUT,"bufsize":-1}
        if subprocess.mswindows:
            su = subprocess.STARTUPINFO()
            su.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            su.wShowWindow = subprocess.SW_HIDE
            kwargs["startupinfo"] = su
            
        ffmpegWithAudioConfig = videoConfig + audioConfig + " %s."+extension
        ffmpegNoAudioConfig = videoConfig + " %s."+extension

        outname = movfile.encode(sys.getfilesystemencoding())
        if tempwavname != None: # Includes Audio
            print "ffmpeg config (audio):",ffmpegWithAudioConfig
            extraArgs = ffmpegWithAudioConfig.strip().split()
            args = [exe,"-f","rawvideo","-pix_fmt","rgb48","-s","%dx%d"%(aw,ah),"-r","%.03f"%fps,"-i","-","-i",tempwavname]
            args.extend(extraArgs[:-1])
            args.extend(["-r","%.03f"%fps,extraArgs[-1]%outname])
            #"-f","mov","-vf","vflip","-vcodec","prores_ks","-profile:v","4","-alpha_bits","0","-vendor","ap4h","-q:v","4","-r","%.03f"%fps,"-acodec","copy",movfile]
        else: # No audio
            # ProRes 4444 with fixed qscale. Can be much smaller and faster to encode
            print "ffmpeg config (no audio):",ffmpegNoAudioConfig
            extraArgs = ffmpegNoAudioConfig.strip().split()
            args = [exe,"-f","rawvideo","-pix_fmt","rgb48","-s","%dx%d"%(aw,ah),"-r","%.03f"%fps,"-i","-","-an"]
            args.extend(extraArgs[:-1])
            args.extend(["-r","%.03f"%fps,extraArgs[-1]%outname])
            #args = [exe,"-f","rawvideo","-pix_fmt","rgb48","-s","%dx%d"%(aw,ah),"-r","%.03f"%fps,"-i","-","-an","-f","mov","-vf","vflip","-vcodec","prores_ks","-profile:v","4","-alpha_bits","0","-vendor","ap4h","-q:v","4","-r","%.03f"%fps,movfile]
            # ProRes 4444 with fixed bitrate. Can be bigger and slower
            #args = [exe,"-f","rawvideo","-pix_fmt","rgb48","-s","%dx%d"%(r.width(),r.height()),"-r","%.03f"%r.fps,"-i","-","-an","-f","mov","-vf","vflip","-vcodec","prores_ks","-profile:v","4","-alpha_bits","0","-vendor","ap4h","-r","%.03f"%r.fps,movfile]
        print "Encoder args:",args
        #print "Subprocess args:",kwargs
        self.encoderProcess = subprocess.Popen(args,**kwargs)
        self.encoderProcess.poll()
        self.stdoutReader = threading.Thread(target=self.stdoutReaderLoop)
        self.stdoutReader.daemon = True
        self.encoderOutput = []
        self.stdoutReader.start()
        self.writer = threading.Thread(target=self.stdoutWriter)
        self.writer.daemon = True
        self.writer.start()
        self.demosaicThread = threading.Thread(target=self.demosaicThreadFunction)
        self.demosaicThread.daemon = True
        self.demosaicThread.start()
        self.writtenFrame = 0
        r.preloadFrame(startFrame)
        r.preloadFrame(startFrame+1) # Preload one ahead
        print "Processing", endFrame, "frames, it may take a while."
        for i in range(endFrame-startFrame+1):
            self.processCommands(block=False)
            f = r.frame(startFrame+i)
            f.lut = lut
            f.lut1d1 = lut1d1
            f.lut1d2 = lut1d2
            if ((startFrame+i+1)<r.frames()):
                r.preloadFrame(startFrame+i+1)
            # Queue job
            if preprocess==self.PREPROCESS_ALL:
                # Must first preprocess with shader
                self.bgiq.put((f,i,1,fw,fh,rgbl,tm,matrix,preprocess,area))
            else:
                self.dq.put((f,i,0,fw,fh,rgbl,tm,matrix,preprocess,area))

            # We need to make sure we don't buffer too many frames. Check what frame the encoder is at
            latest = ""
            if len(self.encoderOutput)>0:
                latest = self.encoderOutput[-1].split()
            frame = None
            if len(latest)>1:
                if latest[0].startswith("frame="):
                    try:
                        frame = int(latest[1])
                    except ValueError:
                        frame = None

            while self.writtenFrame<(i-10):
                if self.endflag or self.cancel:
                    break
                time.sleep(0.1)
            if frame is not None:
                if frame < (self.writtenFrame-10):
                    time.sleep(0.1) # Give encoder some time to empty buffers
            st = float(self.writtenFrame+1)/float(todo)
            print "%.02f%%         \r"%(st*100.0),
            self.jobstatus[jobindex] = st
            if self.endflag or self.cancel:
                break
        if preprocess==self.PREPROCESS_ALL:
            self.bgiq.put("End")
        else:
            self.dq.put(None)
        while (self.writtenFrame+1)<todo:
            time.sleep(0.5)
            st = float(self.writtenFrame+1)/float(todo)
            "%.02f%%         \r"%(st*100.0),
            self.jobstatus[jobindex] = st
            if self.endflag or self.cancel:
                break
        self.dq.join()
        self.writer.join()
        self.jobstatus[jobindex] = 1.0
        print ""
        print extension,"export to",repr(movfile),"finished"
        r.close()

    def stdoutReaderLoop(self):
        chars = []
        buf = ""
        try:
            while 1:
                c = self.encoderProcess.stdout.read(1)
                if len(c)==0:
                    break
                if c[0]=='\n' or c[0]=='\r':
                    buf = ''.join(chars)
                    chars = []
                else:
                    chars.append(c)
                if len(buf)>0:
                    self.encoderOutput.append(buf)
                    #print "Encoder:",buf
                    buf = ""
        except:
            pass
        #print "ENCODER FINISHED!"

    def stdoutWriter(self):
        nextbuf = self.wq.get()
        while nextbuf != None:
            try:
                index,buf = nextbuf
                self.encoderProcess.stdin.write(buf)
                self.writtenFrame = index
            except:
                import traceback
                traceback.print_exc()
                self.cancel = True
            self.wq.task_done()
            time.sleep(0.016) # Yield
            nextbuf = self.wq.get()
        self.wq.task_done()
        #print "WRITER FINISHED!"

    def demosaicThreadFunction(self):
        nextbuf = self.dq.get()
        while nextbuf != None:
            try:
                #self.dq.put((f,r.width(),r.height(),rgbl,tm,matrix))
                nextbuf[0].demosaic()
                self.bgiq.put(nextbuf)
            except:
                import traceback
                traceback.print_exc()
                self.cancel = True
            self.dq.task_done()
            nextbuf = self.dq.get()
        self.bgiq.put(None)
        self.bgiq.join()
        self.dq.task_done()

    def cpuDemosaicPostProcess(self,args):
        jobtype = args[2]
        w = args[3]
        h = args[4]
        if self.svbo == None:
            self.svbo = ui.SharedVbo(1024*16)
        if self.shaderQuality == None:
            self.shaderQuality = ShaderDemosaicCPU()
            self.shaderQuality.context = self.context
        if self.shaderPatternNoise == None:
            self.shaderPatternNoise = ShaderPatternNoise()
            self.shaderPatternNoise.context = self.context
        if self.shaderPreprocess == None:
            self.shaderPreprocess = ShaderPreprocess()
            self.shaderPreprocess.context = self.context
        if self.rgbUploadTex:
            if self.config.isMac() or (self.rgbUploadTex.width != w or self.rgbUploadTex.height != h):
            # On OSX10.9.4, eventually crashes in texture upload unless we reallocate it. OS bug?
                self.rgbUploadTex.free()
                self.rgbImage.free()
                self.rawUploadTex.free()
                self.horizontalPattern.free()
                self.verticalPattern.free()
                self.preprocessTex1.free()
                self.preprocessTex2.free()
                self.rgbUploadTex = None
                self.rgbImage = None
                self.rawUploadTex = None
                self.horizontalPattern = None
                self.verticalPattern = None
                self.preprocessTex1 = None
                self.preprocessTex2 = None
                self.lastPP = None
        if self.rgbUploadTex == None:
            self.rgbUploadTex = GLCompute.Texture((w,h),None,hasalpha=False,mono=False,sixteen=True)
            self.rgbUploadTex.context = self.context
            try: self.rgbImage = GLCompute.Texture((w,h),None,hasalpha=False,mono=False,fp=True)
            except GLError: self.rgbImage = GLCompute.Texture((w,h),None,hasalpha=False,sixteen=True)
            self.rgbImage.context = self.context
            self.rawUploadTex = GLCompute.Texture((w,h),None,hasalpha=False,mono=True,sixteen=True)
            self.rawUploadTex.context = self.context
            self.horizontalPattern = GLCompute.Texture((w,1),None,hasalpha=False,mono=False,fp=True)
            self.horizontalPattern.context = self.context
            self.verticalPattern = GLCompute.Texture((1,h),None,hasalpha=False,mono=False,fp=True)
            self.verticalPattern.context = self.context
            zero = "\0"*w*h*2*4 # 16bit RGBA
            self.preprocessTex1 = GLCompute.Texture((w,h),zero,hasalpha=True,mono=False,sixteen=True)
            self.preprocessTex1.context = self.context
            self.preprocessTex2 = GLCompute.Texture((w,h),zero,hasalpha=True,mono=False,sixteen=True)
            self.preprocessTex2.context = self.context
            self.lastPP = self.preprocessTex2

        if jobtype==0:
            frame,index,jobtype,w,h,rgbl,tm,matrix,preprocess,area = args
            # Shader part of demosaicing
            self.rgbUploadTex.update(frame.rgbimage)
            self.rgbImage.bindfbo()
            self.svbo.bind()
            self.shaderQuality.prepare(self.svbo)
            self.svbo.upload()
            if preprocess==self.PREPROCESS_ALL:
                recover = 0.0
                rgbl = (1.0,1.0,1.0,rgbl[3])
            else:
                recover = 1.0
            if frame.lut1d1 != None and self.currentLut1d1 != frame.lut1d1:
                l = frame.lut1d1
                self.luttex1d1 = GLCompute.Texture1D(l.len(),l.lut().tostring())
                self.luttex1d1.context = self.context
                self.currentLut1d1 = frame.lut1d1
            elif frame.lut1d1 == None and self.luttex1d1 != None:
                self.luttex1d1.free()
                self.luttex1d1 = None
            if frame.lut != None and self.currentLut != frame.lut:
                l = frame.lut
                self.luttex = GLCompute.Texture3D(l.len(),l.lut().tostring())
                self.luttex.context = self.context
                self.currentLut = frame.lut
            elif frame.lut == None and self.luttex != None:
                self.luttex.free()
                self.luttex = None
            if frame.lut1d2 != None and self.currentLut1d2 != frame.lut1d2:
                l = frame.lut1d2
                self.luttex1d2 = GLCompute.Texture1D(l.len(),l.lut().tostring())
                self.luttex1d2.context = self.context
                self.currentLut1d2 = frame.lut1d2
            elif frame.lut1d2 == None and self.luttex1d2 != None:
                self.luttex1d2.free()
                self.luttex1d2 = None
            self.shaderQuality.demosaicPass(self.rgbUploadTex,self.luttex,frame.black,balance=rgbl,white=frame.white,tonemap=tm,colourMatrix=matrix,recover=recover,lut1d1=self.luttex1d1,lut1d2=self.luttex1d2)
            rgb = glReadPixels(area[0],h-(area[1]+area[3]),area[2],area[3],GL_RGB,GL_UNSIGNED_SHORT)
            return (index,rgb)
        elif jobtype==1:            # Predemosaic processing
            frame,index,jobtype,w,h,rgbl,tm,matrix,preprocess,area = args
            frame.convert()
            self.svbo.bind()
            self.shaderPatternNoise.prepare(self.svbo)
            self.shaderPreprocess.prepare(self.svbo)
            self.svbo.upload()
            self.horizontalPattern.bindfbo()
            self.rawUploadTex.update(frame.rawimage)
            self.shaderPatternNoise.draw(w,h,self.rawUploadTex,0,frame.black/65536.0,frame.white/65536.0)
            ssh = self.shaderPatternNoise.calcStripescaleH(w,h)
            self.verticalPattern.bindfbo()
            self.shaderPatternNoise.draw(w,h,self.rawUploadTex,1,frame.black/65536.0,frame.white/65536.0)
            ssv = self.shaderPatternNoise.calcStripescaleV(w,h)
            if self.lastPP == self.preprocessTex2:
                self.preprocessTex1.bindfbo()
                self.shaderPreprocess.draw(w,h,self.rawUploadTex,self.preprocessTex2,self.horizontalPattern,self.verticalPattern,ssh,ssv,frame.black/65536.0,frame.white/65536.0,rgbl,cfa=frame.cfa)
                self.lastPP = self.preprocessTex1
            else:
                self.preprocessTex2.bindfbo()
                self.shaderPreprocess.draw(w,h,self.rawUploadTex,self.preprocessTex1,self.horizontalPattern,self.verticalPattern,ssh,ssv,frame.black/65536.0,frame.white/65536.0,rgbl,cfa=frame.cfa)
                self.lastPP = self.preprocessTex2
            # Now, read out the results as a 16bit raw image and feed to cpu demosaicer
            rawpreprocessed = glReadPixels(0,0,w,h,GL_RED,GL_UNSIGNED_SHORT)
            frame.rawimage = rawpreprocessed
            self.dq.put((frame,index,0,w,h,rgbl,tm,matrix,preprocess,area)) # Queue CPU demosaicing
            return None
        elif jobtype==2:            # DNG preprocessing
            frame,dng,jobtype,w,h,index,target,rgbl = args
            frame.convert()
            ifd = dng.FULL_IFD
            self.svbo.bind()
            self.shaderPatternNoise.prepare(self.svbo)
            self.shaderPreprocess.prepare(self.svbo)
            self.svbo.upload()
            self.horizontalPattern.bindfbo()
            self.rawUploadTex.update(frame.rawimage)
            self.shaderPatternNoise.draw(w,h,self.rawUploadTex,0,frame.black/65536.0,frame.white/65536.0)
            ssh = self.shaderPatternNoise.calcStripescaleH(w,h)
            self.verticalPattern.bindfbo()
            self.shaderPatternNoise.draw(w,h,self.rawUploadTex,1,frame.black/65536.0,frame.white/65536.0)
            ssv = self.shaderPatternNoise.calcStripescaleV(w,h)
            if self.lastPP == self.preprocessTex2:
                self.preprocessTex1.bindfbo()
                self.shaderPreprocess.draw(w,h,self.rawUploadTex,self.preprocessTex2,self.horizontalPattern,self.verticalPattern,ssh,ssv,frame.black/65536.0,frame.white/65536.0,(1.0,1.0,1.0,1.0),control=(0.0,1.0,1.0,1.0),cfa=frame.cfa)
                self.lastPP = self.preprocessTex1
            else:
                self.preprocessTex2.bindfbo()
                self.shaderPreprocess.draw(w,h,self.rawUploadTex,self.preprocessTex1,self.horizontalPattern,self.verticalPattern,ssh,ssv,frame.black/65536.0,frame.white/65536.0,(1.0,1.0,1.0,1.0),control=(0.0,1.0,1.0,1.0),cfa=frame.cfa)
                self.lastPP = self.preprocessTex2
            rawpreprocessed = glReadPixels(0,0,w,h,GL_RED,GL_UNSIGNED_SHORT)
            dng.rawdata = np.frombuffer(rawpreprocessed,dtype=np.uint16).tostring()
            dng.ljpeg = frame.writeljpeg
            self.wq.put((index,target,dng)) # Queue writing
            return None

    def onBgDraw(self,w,h):
        #print "onBgDraw",w,h
        try:
            nextJob = self.bgiq.get_nowait()
            if nextJob == None:
                self.wq.put(None)
                self.wq.join()
            elif nextJob == "End":
                self.dq.put(None)
            else:
                result = self.cpuDemosaicPostProcess(nextJob)
                if result != None:
                    self.wq.put(result)
            self.bgiq.task_done()
        except Queue.Empty:
            pass
            #print "no work to do yet"


