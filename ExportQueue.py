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

import sys,os,threading,Queue,time,math,subprocess

import MlRaw,DNG

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
    JOB_DNG = 0
    JOB_MOV = 1
    def __init__(self,**kwds):
        super(ExportQueue,self).__init__(**kwds)
        self.iq = Queue.Queue()
        self.oq = Queue.Queue()
        self.bgiq = Queue.Queue()
        self.bgoq = Queue.Queue()
        self.jobs = {}
        self.jobstatus = {}
        self.jobindex = 0
        self.endflag = False
        self.ended = False
        self.busy = False
        self.daemon = True
        self.needBgDraw = False
        self.start()
    def end(self):
        self.endflag = True
        self.iq.put(None)
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
    def exportDng(self,rawfile,dngdir,startFrame=0,endFrame=None,bits=16,rgbl=None):
        return self.submitJob(self.JOB_DNG,rawfile,dngdir,startFrame,endFrame,bits,rgbl)
    def exportMov(self,rawfile,movfile,tempwavfile,startFrame=0,endFrame=None,rgbl=None):
        return self.submitJob(self.JOB_MOV,rawfile,movfile,tempwavfile,startFrame,endFrame,rgbl)
    def submitJob(self,*args):
        ix = self.jobindex
        self.jobindex += 1
        self.jobstatus[ix] = 0.0
        job = tuple([ix]+list(args))
        self.jobs[ix] = job
        self.iq.put(ix)
        return ix
    def run(self):
        try:
            while 1: # Wait for the next job in the Queue
                if self.endflag:
                    break
                jobindex = self.iq.get()
                if jobindex != None:
                    self.busy = True
                    try:
                        self.nextJob(self.jobs[jobindex])
                    except:
                        print "Export job failed:"
                        import traceback
                        traceback.print_exc()
                    del self.jobs[jobindex]
                    del self.jobstatus[jobindex]
                    if self.iq.empty():
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
            
    def doExportDng(self,jobindex,args):
        filename,dngdir,startFrame,endFrame,bits,rgbl = args
        todo = endFrame-startFrame+1
        target = dngdir
        r = MlRaw.loadRAWorMLV(filename)
        targfile = os.path.splitext(os.path.split(r.filename)[1])[0]
        target = os.path.join(target,targfile)
        print "DNG export to",target
        r.preloadFrame(startFrame)
        r.preloadFrame(startFrame+1) # Preload one ahead
        for i in range(endFrame-startFrame+1):
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
            self.jobstatus[jobindex] = float(i)/float(todo)
            if self.endflag:
                break
        print "DNG export to",target,"finished"
        r.close()

    def doExportMov(self,jobindex,args):
        self.needBgDraw = True
        filename,movfile,tempwavfile,startFrame,endFrame,rgbl = args
        try:
            self.processExportMov(jobindex,filename,movfile,tempwavfile,startFrame,endFrame,rgbl)
        except:
            import traceback
            traceback.print_exc()
            pass
        # Clean up 
        self.needBgDraw = False
        if tempwavfile!=None:
            os.remove(tempwavfile)
        if self.encoderProcess:
            self.encoderProcess.stdin.close()
            self.encoderProcess = None
        self.encoderOutput = None
        self.stdoutReader = None

    def processExportMov(self,jobindex,filename,movfile,tempwavfile,startFrame,endFrame,rgbl):
        todo = endFrame-startFrame+1
        target = movfile
         
        print "Dummy MOV export to",movfile
        r = MlRaw.loadRAWorMLV(filename)

        if subprocess.mswindows:
            exe = "ffmpeg.exe"
        else:
            exe = "ffmpeg"
        programpath = os.path.abspath(os.path.split(sys.argv[0])[0])
        if getattr(sys,'frozen',False):
            programpath = sys._MEIPASS
        localexe = os.path.join(programpath,exe)
        print localexe
        if os.path.exists(localexe):
            exe = localexe
        kwargs = {"stdin":subprocess.PIPE,"stdout":subprocess.PIPE,"stderr":subprocess.STDOUT}
        if subprocess.mswindows:
            su = subprocess.STARTUPINFO()
            su.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            su.wShowWindow = subprocess.SW_HIDE
            kwargs["startupinfo"] = su
        if tempwavfile != None: # Includes Audio
            args = [exe,"-f","rawvideo","-pix_fmt","rgb48","-s","%dx%d"%(r.width(),r.height()),"-r","%.03f"%r.fps,"-i","-","-i",tempwavfile,"-f","mov","-vf","vflip","-vcodec","prores_ks","-profile:v","3","-r","%.03f"%r.fps,"-acodec","copy",movfile]
        else: # No audio
            args = [exe,"-f","rawvideo","-pix_fmt","rgb48","-s","%dx%d"%(r.width(),r.height()),"-r","%.03f"%r.fps,"-i","-","-an","-f","mov","-vf","vflip","-vcodec","prores_ks","-profile:v","3","-r","%.03f"%r.fps,movfile]
        print "Encoder args:",args
        print "Subprocess args:",kwargs
        self.encoderProcess = subprocess.Popen(args,**kwargs)
        self.encoderProcess.poll()
        self.stdoutReader = threading.Thread(target=self.stdoutReaderLoop)
        self.stdoutReader.daemon = True
        self.encoderOutput = []
        self.stdoutReader.start()

        r.preloadFrame(startFrame)
        r.preloadFrame(startFrame+1) # Preload one ahead
        for i in range(endFrame-startFrame+1):
            f = r.frame(startFrame+i)
            if ((startFrame+i+1)<r.frames()):
                r.preloadFrame(startFrame+i+1)
            # Queue job
            self.bgiq.put(f)
            # Wait for it to be done
            result = self.bgoq.get()
            f.demosaic()    
            self.encoderProcess.stdin.write(f.rgbimage.astype(np.uint16).tostring())

            self.jobstatus[jobindex] = float(i)/float(todo)
            if self.endflag:
                break
        self.jobstatus[jobindex] = 1.0
        print "Dummy MOV export to",movfile,"completed"
        r.close()

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

    def onBgDraw(self,w,h):
        #print "onBgDraw",w,h
        try:
            nextJob = self.bgiq.get_nowait()
            #print "bg job to do",nextJob
            self.bgoq.put(nextJob)
        except Queue.Empty:
            pass
            #print "no work to do yet"


