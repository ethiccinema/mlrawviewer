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

import sys,os,threading,Queue,time,math,subprocess,wave

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
    PREPROCESS_NONE = 0
    PREPROCESS_ALL = 1
    def __init__(self,**kwds):
        super(ExportQueue,self).__init__(**kwds)
        self.iq = Queue.Queue()
        self.bgiq = Queue.Queue()
        self.wq = Queue.Queue()
        self.dq = Queue.Queue()
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
        self.rgbImage = None
        self.svbo = None
        self.pauseState = True
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
                if ix in self.jobs:
                    del self.jobs[ix]
                    del self.jobstatus[ix]
                if self.currentjob == ix:
                    self.cancel = True # Terminate early
            elif ct==self.COMMAND_REMOVE_ALL_JOBS:
                self.jobs = {}
                self.jobstatus = {}
                self.cancel = True
                #print "removed all jobs"
            elif ct==self.COMMAND_PAUSE:
                self.pauseState = True
            elif ct==self.COMMAND_PROCESS:
                self.pauseState = False
            elif ct==self.COMMAND_END:
                self.endflag = True
            once = False

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
        else:
            pass

    def setDngHeader(self,r,d,bits,frame,rgbl):
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
        at(e,DNG.Tag.Compression,1) # No compression
        at(e,DNG.Tag.PhotometricInterpretation,32803) # CFA
        at(e,DNG.Tag.FillOrder,1)
        atm(e,DNG.Tag.Make,r.make()+"\0")
        atm(e,DNG.Tag.Model,r.make()+" "+r.model()+"\0")
        at(e,DNG.Tag.StripOffsets,0)
        at(e,DNG.Tag.Orientation,1)
        at(e,DNG.Tag.SamplesPerPixel,1)
        at(e,DNG.Tag.RowsPerStrip,r.height())
        ifd.RowsPerStrip = r.height()
        at(e,DNG.Tag.StripByteCounts,0)
        at(e,DNG.Tag.PlanarConfiguration,1) # Chunky
        atm(e,DNG.Tag.Software,"MlRawViewer"+"\0")
        if frame.rtc != None:
            se,mi,ho,da,mo,ye = frame.rtc[1:7]
            atm(e,DNG.Tag.DateTime,"%04d:%02d:%02d %02d:%02d:%02d\0"%(ye+1900,mo,da,ho,mi,se))
        #atm(e,DNG.Tag.DateTime,"1988:10:01 23:23:23")
        atm(e,DNG.Tag.CFARepeatPatternDim,(2,2)) # No compression
        atm(e,DNG.Tag.CFAPattern,(0,1,1,2)) # No compression
        at(e,DNG.Tag.EXIF_IFD,0)
        atm(e,DNG.Tag.DNGVersion,(1,4,0,0))
        atm(e,DNG.Tag.UniqueCameraModel,r.make()+" "+r.model()+"\0")
        atm(e,DNG.Tag.LinearizationTable,[i for i in range(2**14-1)])
        at(e,DNG.Tag.BlackLevel,r.black)
        at(e,DNG.Tag.WhiteLevel,r.white)
        atm(e,DNG.Tag.DefaultCropOrigin,(0,0))
        atm(e,DNG.Tag.DefaultCropSize,(r.width(),r.height()))
        m = [(int(v*10000),10000) for v in r.colorMatrix.A1]
        atm(e,DNG.Tag.ColorMatrix1,m)
        if rgbl==None: # Pick a default
            atm(e,DNG.Tag.AsShotNeutral,((473635,1000000),(1000000,1000000),(624000,1000000)))
        else:
            asnred = int(1000000/rgbl[0])
            asngreen = int(1000000/rgbl[1])
            asnblue = int(1000000/rgbl[2])
            atm(e,DNG.Tag.AsShotNeutral,((asnred,1000000),(asngreen,1000000),(asnblue,1000000)))
            ev = int(1000000*math.log(rgbl[3],2.0))
            at(e,DNG.Tag.BaselineExposure,(0,1000000)) # Not yet used by dcraw-based tools :-(
            at(e,DNG.Tag.BaselineExposureOffset,(ev,1000000)) # Not yet used by dcraw-based tools :-(
        at(e,DNG.Tag.FrameRate,(r.fpsnum,r.fpsden))
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

    def tempEncoderWav(self,wavfile,fps,tempname,inframe,outframe,audioOffset):
        wav = wave.open(wavfile,'r')
        tempwav = wave.open(tempname,'w')
        tempwav.setparams(wav.getparams())
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
        os.mkdir(dngdir)
        target = dngdir
        r = MlRaw.loadRAWorMLV(filename)
        if endFrame == None:
            endFrame = r.frames()
        todo = endFrame-startFrame+1
        if r.audioFrames()>0:
            # Must index the whole file in order that we have the wav file
            while r.indexingStatus()<1.0:
                time.sleep(0.1) 
        if os.path.exists(wavfile):
            d = file(wavfile,'rb').read()
            rhead = os.path.splitext(os.path.split(filename)[1])[0]
            outwavname = os.path.join(dngdir, rhead + ".WAV")
            self.tempEncoderWav(wavfile,r.fps,outwavname,startFrame,endFrame,audioOffset)
        targfile = os.path.splitext(os.path.split(r.filename)[1])[0]
        target = os.path.join(target,targfile)
        print "DNG export to",target,"started"
        r.preloadFrame(startFrame)
        r.preloadFrame(startFrame+1) # Preload one ahead
        for i in range(endFrame-startFrame+1):
            self.processCommands(block=False)
            f = r.frame(startFrame+i)
            d = DNG.DNG()
            self.setDngHeader(r,d,bits,f,rgbl)
            ifd = d.FULL_IFD
            if ((startFrame+i+1)<r.frames()):
                r.preloadFrame(startFrame+i+1)
            if bits==14:
                ifd._strips = [np.frombuffer(f.rawdata,dtype=np.uint16).byteswap().tostring()]
            elif bits==16:
                f.convert() # Will block if still processing
                ifd._strips = [np.frombuffer(f.rawimage,dtype=np.uint16).tostring()]
            d.writeFile(target+"_%06d.dng"%i)
            st = float(i)/float(todo)
            #print "%.02f%%"%(st*100.0)
            self.jobstatus[jobindex] = st
            if self.endflag or self.cancel:
                break
        print "DNG export to",target,"finished"
        r.close()

    def doExportMov(self,jobindex,args):
        self.needBgDraw = True
        filename,movfile,wavfile,startFrame,endFrame,audioOffset,rgbl,tm,matrix,preprocess = args
        try:
            self.processExportMov(jobindex,filename,movfile,wavfile,startFrame,endFrame,audioOffset,rgbl,tm,matrix,preprocess)
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

    def processExportMov(self,jobindex,filename,movfile,wavfile,startFrame,endFrame,audioOffset,rgbl,tm,matrix,preprocess):
        target = movfile
        print "MOV export to",movfile,"started"
        tempwavname = None 
        r = MlRaw.loadRAWorMLV(filename)
        if endFrame == None:
            endFrame = r.frames()
        todo = endFrame-startFrame+1
        if r.audioFrames()>0:
            # Must index the whole file in order that we have the wav file
            while r.indexingStatus()<1.0:
                time.sleep(0.1) 
        if os.path.exists(wavfile): 
            tempwavname = movfile[:-4] + ".WAV"
            self.tempEncoderWav(wavfile,r.fps,tempwavname,startFrame,endFrame,audioOffset)

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
        if tempwavname != None: # Includes Audio
            args = [exe,"-f","rawvideo","-pix_fmt","rgb48","-s","%dx%d"%(r.width(),r.height()),"-r","%.03f"%r.fps,"-i","-","-i",tempwavname,"-f","mov","-vf","vflip","-vcodec","prores_ks","-profile:v","4","-alpha_bits","0","-vendor","ap4h","-q:v","4","-r","%.03f"%r.fps,"-acodec","copy",movfile]
        else: # No audio
            # ProRes 4444 with fixed qscale. Can be much smaller and faster to encode
            args = [exe,"-f","rawvideo","-pix_fmt","rgb48","-s","%dx%d"%(r.width(),r.height()),"-r","%.03f"%r.fps,"-i","-","-an","-f","mov","-vf","vflip","-vcodec","prores_ks","-profile:v","4","-alpha_bits","0","-vendor","ap4h","-q:v","4","-r","%.03f"%r.fps,movfile]
            # ProRes 4444 with fixed bitrate. Can be bigger and slower
            #args = [exe,"-f","rawvideo","-pix_fmt","rgb48","-s","%dx%d"%(r.width(),r.height()),"-r","%.03f"%r.fps,"-i","-","-an","-f","mov","-vf","vflip","-vcodec","prores_ks","-profile:v","4","-alpha_bits","0","-vendor","ap4h","-r","%.03f"%r.fps,movfile]
        #print "Encoder args:",args
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
        for i in range(endFrame-startFrame+1):
            self.processCommands(block=False)
            f = r.frame(startFrame+i)
            if ((startFrame+i+1)<r.frames()):
                r.preloadFrame(startFrame+i+1)
            # Queue job
            if preprocess==self.PREPROCESS_ALL:
                # Must first preprocess with shader
                self.bgiq.put((f,i,1,r.width(),r.height(),rgbl,tm,matrix))
            else:
                self.dq.put((f,i,0,r.width(),r.height(),rgbl,tm,matrix))

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
            if frame != None:
                if frame < (self.writtenFrame-10):
                    time.sleep(0.1) # Give encoder some time to empty buffers
            st = float(self.writtenFrame+1)/float(todo)
            #print "%.02f%%"%(st*100.0)
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
            #print "%.02f%%"%(st*100.0)
            self.jobstatus[jobindex] = st
            if self.endflag or self.cancel:
                break
        self.dq.join()
        self.jobstatus[jobindex] = 1.0
        print "MOV export to",movfile,"finished"
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
        frame,index,jobtype,w,h,rgbl,tm,matrix = args
        if self.svbo == None:
            self.svbo = ui.SharedVbo(1024*16)
        if self.shaderQuality == None:
            self.shaderQuality = ShaderDemosaicCPU()
        if self.shaderPatternNoise == None:
            self.shaderPatternNoise = ShaderPatternNoise()
        if self.shaderPreprocess == None:
            self.shaderPreprocess = ShaderPreprocess()
        if self.rgbUploadTex:
            if self.rgbUploadTex.width != w or self.rgbUploadTex.height != h:
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
            try: self.rgbImage = GLCompute.Texture((w,h),None,hasalpha=False,mono=False,fp=True)
            except GLError: self.rgbImage = GLCompute.Texture((w,h),None,hasalpha=False,sixteen=True)
            self.rawUploadTex = GLCompute.Texture((w,h),None,hasalpha=False,mono=True,sixteen=True)
            self.horizontalPattern = GLCompute.Texture((w,1),None,hasalpha=False,mono=False,fp=True)
            self.verticalPattern = GLCompute.Texture((1,h),None,hasalpha=False,mono=False,fp=True)
            zero = "\0"*w*h*2*4 # 16bit RGBA
            self.preprocessTex1 = GLCompute.Texture((w,h),zero,hasalpha=True,mono=False,sixteen=True)
            self.preprocessTex2 = GLCompute.Texture((w,h),zero,hasalpha=True,mono=False,sixteen=True)
            self.lastPP = self.preprocessTex2

        if jobtype==0:
            # Shader part of demosaicing
            self.rgbUploadTex.update(frame.rgbimage)
            self.rgbImage.bindfbo()
            self.svbo.bind()
            self.shaderQuality.prepare(self.svbo)
            self.svbo.upload()
            self.shaderQuality.demosaicPass(self.rgbUploadTex,frame.black,balance=rgbl,white=frame.white,tonemap=tm,colourMatrix=matrix)
            rgb = glReadPixels(0,0,w,h,GL_RGB,GL_UNSIGNED_SHORT)
            return (index,rgb)
        elif jobtype==1:            # Predemosaic processing
            frame.convert()
            self.svbo.bind()
            self.shaderPatternNoise.prepare(self.svbo)
            self.shaderPreprocess.prepare(self.svbo)
            self.svbo.upload()
            self.horizontalPattern.bindfbo()
            self.rawUploadTex.update(frame.rawimage)
            self.shaderPatternNoise.draw(w,h,self.rawUploadTex,0,frame.black/65536.0,frame.white/65536.0) 
            horiz = glReadPixels(0,0,w,1,GL_RGB,GL_FLOAT)
            low = horiz[:,0,0]
            high = horiz[:,0,1]
            horl = low.mean()
            horh = high.mean()
            self.verticalPattern.bindfbo()
            self.shaderPatternNoise.draw(w,h,self.rawUploadTex,1,frame.black/65536.0,frame.white/65536.0) 
            vert = glReadPixels(0,0,1,h,GL_RGB,GL_FLOAT)
            low = vert[0,:,0]
            high = vert[0,:,1]
            verl = low.mean()
            verh = high.mean()
            if self.lastPP == self.preprocessTex2:
                self.preprocessTex1.bindfbo()
                self.shaderPreprocess.draw(w,h,self.rawUploadTex,self.preprocessTex2,self.horizontalPattern,self.verticalPattern,horl,horh,verl,verh,frame.black/65536.0,frame.white/65536.0,rgbl)
                self.lastPP = self.preprocessTex1
            else:
                self.preprocessTex2.bindfbo()
                self.shaderPreprocess.draw(w,h,self.rawUploadTex,self.preprocessTex1,self.horizontalPattern,self.verticalPattern,horl,horh,verl,verh,frame.black/65536.0,frame.white/65536.0,rgbl)
                self.lastPP = self.preprocessTex2
            # Now, read out the results as a 16bit raw image and feed to cpu demosaicer
            rawpreprocessed = glReadPixels(0,0,w,h,GL_RED,GL_UNSIGNED_SHORT)
            frame.rawimage = rawpreprocessed
            self.dq.put((frame,index,0,w,h,rgbl,tm,matrix)) # Queue CPU demosaicing
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


