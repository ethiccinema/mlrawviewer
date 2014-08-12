"""
MlRaw.py
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

# standard python imports
import sys,struct,os,math,time,threading,Queue,traceback,wave,multiprocessing,mutex,cPickle

# MlRawViewer imports
import DNG
from PerformanceLog import PLOG
PLOG_CPU = 0

# numpy. Could be missing
try:
    import numpy as np
except Exception,err:
    print """There is a problem with your python environment.
I Could not import the numpy module.
On Debian/Ubuntu try "sudo apt-get install python-numpy"
"""
    sys.exit(1)

try:
    """
    This C extension is faster way to do the 14-to-16bit
    conversion that with numpy bitops, but fall back to
    numpy in case it hasn't been compiled
    """
    import bitunpack
    if ("__version__" not in dir(bitunpack)) or bitunpack.__version__!="2.0":
        print """

!!! Wrong version of bitunpack found !!!
!!! Please rebuild latest version. !!!

"""
        raise
except:
    print """

!!! Please build bitunpack module !!!

"""
    raise

class SerialiseCPUDemosaic(object):
    class DemosaicWorker(threading.Thread):
        def __init__(self,jobq):
            threading.Thread.__init__(self)
            self.daemon = True
            self.jobq = jobq
            self.start()
        def run(self):
            while True:
                job = self.jobq.get()
                bitunpack.demosaic(*job)
                self.jobq.task_done()

    def __init__(self):
        self.mutex = mutex.mutex()
        self.serq = Queue.Queue(1) # Using as Mutex
        self.jobq = Queue.Queue()
        pool = [self.DemosaicWorker(self.jobq) for i in range(multiprocessing.cpu_count())]
        self.demosaicer = None
        self.dw = 0
        self.dh = 0
    def getdemosaicer(self,width,height):
        if self.serq.empty():
            raise # Cannot call this if you don't hold the mutex
        if self.demosaicer != None:
            if width==self.dw and height==self.dh:
                return self.demosaicer
            else:
                del self.demosaicer # Wrong size
                self.demosaicer = None
        self.demosaicer = bitunpack.demosaicer(width,height)
        self.dw = width
        self.dh = height
        return self.demosaicer

    def doDemosaic(self,demosaicer,width,height):
        # Submit 16 jobs to be spread amongst available threads
        bw = (width/4)
        bw = bw + (4-bw%4) # Round up
        bh = height/4
        bh = bh + (bh%2) # Round up
        for y in range(4):
            for x in range(4):
                aw = bw
                ah = bh
                re = (x+1)*bw
                if re>=width:
                    aw -= (re-width)
                be = (y+1)*bh
                if be>=height:
                    ah -= (be-height)
                #print x*bw,y*bh,x*bw+aw,y*bh+ah,width,height,aw,ah,re,be
                self.jobq.put((demosaicer,x*bw,y*bh,aw,ah))
        self.jobq.join()

    def demosaic14(self,rawdata,width,height,black,byteSwap=0):
        self.serq.put(True) # Let us run
        demosaicer = self.getdemosaicer(width,height)
        bitunpack.predemosaic14(demosaicer,rawdata,width,height,black,byteSwap)
        self.doDemosaic(demosaicer,width,height)
        result = bitunpack.postdemosaic(demosaicer)
        self.serq.get() # Let someone else work
        return np.frombuffer(result,dtype=np.float32)

    def demosaic16(self,rawdata,width,height,black,byteSwap=0):
        self.serq.put(True) # Let us run
        demosaicer = self.getdemosaicer(width,height)
        bitunpack.predemosaic16(demosaicer,rawdata,width,height,black,byteSwap)
        self.doDemosaic(demosaicer,width,height)
        result = bitunpack.postdemosaic(demosaicer)
        self.serq.get() # Let someone else work
        return np.frombuffer(result,dtype=np.float32)

DemosaicThread = SerialiseCPUDemosaic()

def testdemosaicer():
    d = bitunpack.demosaicer(128,128)
    del d
    d1 = bitunpack.demosaicer(3000,2000)
    d2 = bitunpack.demosaicer(1024,1024)
    del d2
    del d1
    d3 = bitunpack.demosaicer(1024,768)
    buf = (np.arange(1024*768,dtype=np.uint32)%256).astype(np.uint8)
    len14 = 1024*768*14/8
    len16 = 1024*768*2
    bitunpack.predemosaic14(d3,buf[:len14],1024,768,2000,0)
    bitunpack.predemosaic16(d3,buf[:len16],1024,768,2000,0)
    dembuf = DemosaicThread.demosaic14(buf[:len14],1024,768,2000,0)
    #print buf,dembuf.shape,dembuf.reshape((1024,768,3))[:,300]

#testdemosaicer()
#print "test demosaicer done"

def unpacks14np16(rawdata,width,height,byteSwap=0):
    tounpack = width*height*14/8
    unpacked,stats = bitunpack.unpack14to16(rawdata[:tounpack],byteSwap)
    return np.frombuffer(unpacked,dtype=np.uint16),stats

def demosaic14(rawdata,width,height,black,byteSwap=0):
    raw = DemosaicThread.demosaic14(rawdata,width,height,black,byteSwap)
    return np.frombuffer(raw,dtype=np.float32)

def demosaic16(rawdata,width,height,black,byteSwap=0):
    raw = DemosaicThread.demosaic16(rawdata,width,height,black,byteSwap)
    return np.frombuffer(raw,dtype=np.float32)

class FrameConverter(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.daemon = True
        self.iq = Queue.Queue()
        self.start()
    def process(self,frame):
        self.iq.put(frame)
    def run(self):
        try:
            while 1:
                nextFrame = self.iq.get()
                PLOG(PLOG_CPU,"Threaded convert for frame starts")
                nextFrame.convertQ.put(nextFrame._convert())
                PLOG(PLOG_CPU,"Threaded convert for frame complete")
        except:
            pass # Avoid shutdown errors

FrameConverterThread = FrameConverter()

class Frame:
    def __init__(self,rawfile,rawdata,width,height,black,white,byteSwap=0,bitsPerSample=14,bayer=True,rgb=False,convert=True,rtc=None,lens=None,expo=None,wbal=None):
        #print "opening frame",len(rawdata),width,height
        #print width*height
        self.rawfile = rawfile
        self.black = black
        self.white = white
        self.rawdata = rawdata
        self.width = width
        self.height = height
        self.canDemosaic = True
        self.rawimage = None
        self.byteSwap = byteSwap
        self.bitsPerSample = bitsPerSample
        self.conversionResult = None
        self.convertQueued = False
        self.rtc = rtc
        self.lens = lens
        self.expo = expo
        self.wbal = wbal
	self.rawwbal = (1.0,1.0,1.0)
        self.convertQ = Queue.Queue(1)
        if bayer==False and rgb==True:
            self.rgbimage = rawdata
        else:
            self.rgbimage = None
        if convert:
            self.convertQueued = True
            FrameConverterThread.process(self)

    def convert(self):
        if not self.convertQueued:
            self.convertQueued = True
            FrameConverterThread.process(self)

        if self.conversionResult == None:
            self.conversionResult = self.convertQ.get() # Will block until conversion completed
        return self.conversionResult

    def _convert(self):
        if self.rgbimage != None:
            return True # No need to convert anything
        if self.rawimage != None:
            return True # Done already
        if self.rawdata != None:
            if self.bitsPerSample == 14:
                self.rawimage,self.framestats = unpacks14np16(self.rawdata,self.width,self.height,self.byteSwap)
            elif self.bitsPerSample == 16:
                self.rawimage,self.framestats = np.fromstring(self.rawdata,dtype=np.uint16),(0,0)
        else:
            rawimage = np.empty(self.width*self.height,dtype=np.uint16)
            rawimage.fill(self.black)
            self.rawimage = rawimage.tostring()
        return True
    def demosaic(self):
        # CPU based demosaic -> SLOW!
        if self.rgbimage != None:
            return # Done already
        elif self.rawimage != None:
            # Already converted 14bit to 16bit, or preprocessed
            self.rgbimage = demosaic16(self.rawimage,self.width,self.height,self.black,byteSwap=0)
        elif self.rawdata != None:
            if self.bitsPerSample == 14:
                self.rgbimage = demosaic14(self.rawdata,self.width,self.height,self.black,self.byteSwap)
            elif self.bitsPerSample == 16:
                self.rgbimage = demosaic16(self.rawdata,self.width,self.height,self.black,byteSwap=0) # Hmm...what about byteSwapping?
        else:
            self.rgbimage = np.zeros(self.width*self.height*3,dtype=np.uint16).tostring()
    def thumb(self):
        """
        Try to make a thumbnail from the data we have
        """
        PLOG(PLOG_CPU,"Frame thumb gen starts")
        if self.rgbimage!=None:
            # Subsample the rgbimage at about 1/8th size
            nrgb = self.rgbimage.reshape((self.height,self.width,3)).astype(np.float32)
            # Random brightness and colour balance
            ssnrgb = ((64.0/65536.0)*np.array([2.0,1.0,2.0]))*nrgb[::8,::8,:]
            # Tone map
            ssnrgb = ssnrgb/(1.0 + ssnrgb)
            # Map to 16bit uint range
            PLOG(PLOG_CPU,"Frame thumb gen done")
            return (ssnrgb*65536.0).astype(np.uint16)
        if self.rawdata and self.bitsPerSample==14:
            # Extract low-quality downscaled RGB image
            # from packed 14bit bayer data
            # Take first 2 14bit values from every block of 8
            # (packed into 14 bytes) on 2 out of 8 rows.
            # That gives R,G1,G2,B values. Make 1 pixel from those
            h = 8*(self.height/8)
            bayer = np.fromstring(self.rawdata,dtype=np.uint16).reshape(self.height,(self.width*7)/8)[:h,:].astype(np.uint16) # Clip to height divisible by 8
            r1 = bayer[::8,::7]
            r2 = bayer[::8,1::7]
            b1 = bayer[1::8,::7]
            b2 = bayer[1::8,1::7]
            nrgb = np.zeros(shape=(self.height/8,self.width/8,3),dtype=np.uint16)+self.black
            nrgb[:,:,0] = r1>>2
            nrgb[:,:,1] = ((r1&0x3)<<12) | (r2>>4)
            nrgb[:,:,2] = ((b1&0x3)<<12) | (b2>>4)
            # Random brightness and colour balance
            ssnrgb = ((64.0/65536.0)*np.array([2.0,1.0,1.5]))*(nrgb.astype(np.float32)-self.black)
            ssnrgb = np.clip(ssnrgb,0.0,1000000.0)
            # Tone map
            ssnrgb = ssnrgb/(1.0 + ssnrgb)
            # Map to 16bit uint range
            PLOG(PLOG_CPU,"Frame thumb gen done")
            return (ssnrgb*65536.0).astype(np.uint16)
        PLOG(PLOG_CPU,"Frame thumb gen done")

def colorMatrix(raw_info):
    vals = np.array(raw_info[-19:-1]).astype(np.float32)
    nom = vals[::2]
    denom = vals[1::2]
    scaled = (nom/denom).reshape((3,3))
    XYZToCam = np.matrix(scaled)
    camToXYZ = XYZToCam.getI()
    XYZtosRGB = np.matrix([[3.2404542,-1.5371385,-0.4985314],
                           [-0.9692660,1.8760108,0.0415560],
                           [0.0556434,-0.2040259,1.0572252]])
    camToLinearsRGB = XYZtosRGB * camToXYZ
    #print "colorMatrix:",camTosRGB
    return XYZToCam

def getRawFileSeries(basename):
    dirname,filename = os.path.split(basename)
    base = filename[:-2]
    ld = os.listdir(dirname)
    samenamefiles = [n for n in ld if n[:-2]==base and n!=filename and n[-4:].lower()!=".mrx"]
    #idxname = base[:-1]+"IDX"
    #indexfile = [n for n in ld if n==idxname]
    allfiles = [filename]
    #allfiles.extend(indexfile)
    samenamefiles.sort()
    allfiles.extend(samenamefiles)
    return dirname,allfiles

"""
An image sequence is a read-only file set
We also can try to create and restore an own metadata files
which contain additional derived or user-set data. Examples include:
- Thumbnail or thumbnails
- Frame index
- External audio file link
- Audio sync offset
- Colour balance and tone mapping preference
- FPS overide setting
"""

class ImageSequence(object):
    def __init__(self,userMetadataFilename=None,**kwds):
        self._metadataLock = threading.Lock()
        self._userMetadata = {}
        self._userMetadataFilename = userMetadataFilename
        self._metadataLock.acquire()
        self._readUserMetadata()
        self._metadataLock.release()
        super(ImageSequence,self).__init__(**kwds)
    def getMeta(self,key):
        #print "getMeta acquiring lock",key
        self._metadataLock.acquire()
        #print "got lock"
        ret = self._userMetadata.get(key,None)
        #print "getmeta releasing lock"
        self._metadataLock.release()
        #print "getmeta done"
        return ret
    def setMetaValues(self,keyvals):
        #print "setMetaValues acquiring lock"
        self._metadataLock.acquire()
        #print "setMetaValue got lock"
        count = 0
        for k in keyvals.keys():
            val = keyvals[k]
            #print k,len(val)
            old = self._userMetadata.get(k,None)
            if old != None and val == old:
                continue
            self._userMetadata[k] = val
            count += 1
        #print count
        if count>0:
            self._writeUserMetadata()
        #print "setMetaValues releaseing lock"
        self._metadataLock.release()
        #print "setMetaValues done"
    def setMeta(self,key,value):
        #print "setMeta acquiring lock",key
        self._metadataLock.acquire()
        #print "setMeta got lock"
        old = self._userMetadata.get(key,None)
        if old != None and value == old:
            #print "setMeta nothing to do, releasing lock"
            self._metadataLock.release()
            #print "setMeta done"
            return # Nothing to do
        self._userMetadata[key] = value
        self._writeUserMetadata()
        #print "setMeta releasing lock"
        self._metadataLock.release()
        #print "setMeta done"
    def _readUserMetadata(self):
        #print "Trying to read user metadata file",self._userMetadataFilename
        try:
            if self._userMetadataFilename == None: return
            if os.path.exists(self._userMetadataFilename):
                userMetadataFile = file(self._userMetadataFilename,'rb')
                self._userMetadata = cPickle.load(userMetadataFile)
                userMetadataFile.close()
                #print "Read user metadata file. Contents:",len(self._userMetadata),self._userMetadata.keys()
        except:
            self._userMetadata = {}
            import traceback
            traceback.print_exc()
        #print "Read user metadata"
    def _writeUserMetadata(self):
        #print "Trying to write user metadata",len(self._userMetadata)
        try:
            if self._userMetadataFilename == None: return
            if len(self._userMetadata)>0:
                userMetadataFile = file(self._userMetadataFilename,'wb')
                cPickle.dump(self._userMetadata,userMetadataFile,protocol=cPickle.HIGHEST_PROTOCOL)
                userMetadataFile.close()
        except:
            import traceback
            traceback.print_exc()
        #print "User metadata written"
    @staticmethod
    def userMetadataNameFromOriginal(original):
        return os.path.splitext(original)[0]+".MRX"

"""
ML RAW - need to handle spanning files
"""
class MLRAW(ImageSequence):
    def __init__(self,filename,preindex=False,**kwds):
        #print "Opening MLRAW file",filename
        self.filename = filename
        dirname,allfiles = getRawFileSeries(filename)
        indexfile = os.path.join(dirname,allfiles[-1])
        self.indexfile = file(indexfile,'rb')
        self.indexfile.seek(-192,os.SEEK_END)
        footerdata = self.indexfile.read(192)
        self.footer = struct.unpack("4shhiiiiii",footerdata[:8*4])
        self.fps = float(self.footer[6])*0.001
        if self.footer>=23974 and self.footer<=23976:
            self.fpsnum = 24000
            self.fpsden = 1001
        else:
            self.fpsnum = self.footer[6]
            self.fpsden = 1000
        #print "FPS:",self.fps
        self.info = struct.unpack("40i",footerdata[8*4:])
        #print self.footer,self.info
        self.black = self.info[7]
        self.white = self.info[8]
        self.cropOrigin = (self.info[9],self.info[10])
        self.cropSize = (self.info[11],self.info[12])
        self.activeArea = tuple(self.info[13:17])
        self.colorMatrix = colorMatrix(self.info)
        self.whiteBalance = None # Not available in RAW
        self.brightness = 1.0
        #print "Black level:", self.black, "White level:", self.white
        self.framefiles = []
        for framefilename in allfiles:
            fullframefilename = os.path.join(dirname,framefilename)
            framefile = file(fullframefilename,'rb')
            framefile.seek(0,os.SEEK_END)
            framefilelen = framefile.tell()
            self.framefiles.append((framefile,framefilelen))
        self.firstFrame = self._loadframe(0,convert=False)
        self.preloader = threading.Thread(target=self.preloaderMain)
        self.preloaderArgs = Queue.Queue(2)
        self.preloaderResults = Queue.Queue(2)
        self.preloader.daemon = True
        self.preloader.start()
        super(MLRAW,self).__init__(userMetadataFilename=ImageSequence.userMetadataNameFromOriginal(indexfile),**kwds)
    def close(self):
        self.preloaderArgs.put(None) # So that preloader thread exits
        self.preloader.join() # Wait for it to finish
        self.indexfile.close()
        for filehandle,filelen in self.framefiles:
            filehandle.close()
    def indexingStatus(self):
        return 1.0 # RAW doesn't get indexed. It is sequential
    def description(self):
        return self.filename
    def width(self):
        return self.footer[1]
    def height(self):
        return self.footer[2]
    def frames(self):
        return self.footer[4]
    def make(self):
        return "Canon"
    def model(self):
        return "EOS"
    def audioFrames(self):
        return 0
    def preloaderMain(self):
        while 1:
            arg = self.preloaderArgs.get() # Will wait for a job
            if arg==None:
                break
            frame = self._loadframe(arg)
            self.preloaderResults.put((arg,frame))
    def preloadFrame(self,index):
        self.preloaderArgs.put(index)
    def isPreloadedFrameAvailable(self):
        return not self.preloaderResults.empty()
    def nextFrame(self):
        return self.preloaderResults.get()
    def frame(self,index):
        preloadedindex = -1
        frame = None
        while preloadedindex!=index:
            preloadedindex,frame = self.preloaderResults.get()
            if preloadedindex==index:
                break
            self.preloadFrame(index)
        return frame
    def _loadframe(self,index,convert=True):
        if index>=0 and index<self.frames():
            offset = index*self.footer[3]
            needed = self.footer[3]
            framedata = ""
            for filehandle,filelen in self.framefiles:
                if offset>=filelen:
                    offset -= filelen
                    continue
                filecontains = filelen-offset
                needfromfile = min(filecontains,needed)
                filehandle.seek(offset)
                PLOG(PLOG_CPU,"Reading frame %d size %d"%(index,needfromfile))
                newframedata = filehandle.read(needfromfile)
                PLOG(PLOG_CPU,"Read frame %d size %d"%(index,needfromfile))
                needed -= len(newframedata)
                framedata += newframedata
                if needed==0:
                    break
            if needed!=0:
                return ""
            return Frame(self,framedata,self.width(),self.height(),self.black,self.white,convert=convert)
        return ""


"""
ML MLV format - need to handle spanning files
"""
class MLV(ImageSequence):
    class BlockType:
        FileHeader = 0x49564c4d
        VideoFrame = 0x46444956
        AudioFrame = 0x46445541
        RawInfo = 0x49574152
        WavInfo = 0x73866587
        ExposureInfo = 0x4f505845
        LensInfo = 0x534e454c
        RealTimeClock = 0x49435452
        Identity = 0x544e4449
        XREF = 0x46455258
        Info = 0x4f464e49
        DualISOInfo = 0x79837368
        Empty = 0x76768578
        Marker = 0x75826577
        OffsetCorrectionFrame = 0x83707079
        Vignette = 0x78717386
        WhiteBalance = 0x4c414257
        ElectronicLevel = 0x4c564c45
        Mark = 0x4b52414d
        Styl = 0x4c595453
        Wavi = 0x49564157
        Null = 0x4c4c554e

    BlockTypeNames = [n for n in dir(BlockType) if n!="__doc__" and n!="__module__"]
    BlockTypeValues = [getattr(BlockType,n) for n in BlockTypeNames]
    BlockTypeLookup = dict(zip(BlockTypeValues,BlockTypeNames))

    def __init__(self,filename,preindex=True,**kwds):
        self.filename = filename
        #print "Opening MLV file",filename
        dirname,allfiles = getRawFileSeries(filename)
        mlvfile = file(filename,'rb')
        self.fhs = [mlvfile] # Creates an fh-index to fh table for the index data
        self.wav = None
        self.whiteBalance = None # Not yet read from MLVs
        self.brightness = 1.0 # Not meaningful in MLV
        self.framepos = {}
        self.audioframepos = {}
        self.metadata = [] # Store small info blocks so frames can reference them
        self.currentExpo = None
        self.currentWbal = None
        self.currentLens = None
        self.currentRtc = None
        self.identity = ("Canon","EOS","",None)
        self.allParsed = False
        header,raw,parsedTo,size,ts = self.parseFile(0,self.framepos)
        self.fps = float(header[16])/float(header[17])
        self.fpsnum = header[16]
        self.fpsden = header[17]
        if header[16]==23976:
            self.fpsnum = 24000
            self.fpsden = 1001
        #print "FPS:",self.fps,"(%d/%d)"%(self.fpsnum,self.fpsden)
        self.framecount = header[14]
        self.audioFrameCount = header[15]
        self.preindexed = 0
        self.header = header
        self.raw = raw
        self.ts = ts
        self.files = [(0,0,header[14],header,parsedTo, size)]
        self.totalSize = size
        self.totalParsed = parsedTo
        self.firstFrame = self._loadframe(0,convert=False)
        for spanfilename in allfiles[1:]:
            fullspanfile = os.path.join(dirname,spanfilename)
            #print fullspanfile
            spanfile = file(fullspanfile,'rb')
            self.fhs.append(spanfile)
            header,raw,parsedTo,size,ts = self.parseFile(len(self.fhs)-1,self.framepos)
            #print fullspanfile,len(header)
            self.files.append((len(self.fhs)-1,self.framecount,header[14],header,parsedTo, size))
            self.framecount += header[14]
            self.audioFrameCount += header[15]
            self.totalSize += size
            self.totalParsed += parsedTo
        super(MLV,self).__init__(userMetadataFilename=ImageSequence.userMetadataNameFromOriginal(filename),**kwds)
        oldframepos = self.getMeta("frameIndex_v1")
        if oldframepos != None and self.wav==None:
            # If there is wav, it means we must reindex to generate it
            #print "Existing index data found"
            self.framepos = oldframepos
            self.metadata = self.getMeta("sequenceMetadata_v1")
            self.allParsed = True # No need to reindex
            #print "Loaded index data"
        self.preloader = None
        self.preindexing = preindex
        #print "Audio frame count",self.audioFrameCount
        self.initPreloader()
    def indexingStatus(self):
        if self.preindexing:
            return float(self.totalParsed)/float(self.totalSize)
        else:
            return 1.0
    def initPreloader(self):
        if (self.preloader == None):
            self.preloader = threading.Thread(target=self.preloaderMain)
            self.preloaderArgs = Queue.Queue(2)
            self.preloaderResults = Queue.Queue(2)
            self.preloader.daemon = True
            self.preloader.start()
    def close(self):
        self.preloaderArgs.put(None) # So that preloader thread exits
        self.preloader.join() # Wait for it to finish
        for fhi,firstframe,frames,header,parsedTo,size in self.files:
            self.fhs[fhi].close()
    def currentMetadata(self):
        return (self.currentRtc,self.currentExpo,self.currentWbal,self.currentLens)
    def toMetadata(self,ix):
        return {"rtc":self.metadata[ix[0]],
                "expo":self.metadata[ix[1]],
                "wbal":self.metadata[ix[2]],
                "lens":self.metadata[ix[3]]}
    def parseFile(self,fhi,framepos):
        fh = self.fhs[fhi]
        fh.seek(0,os.SEEK_END)
        size = fh.tell()
        pos = 0
        count = 0
        header = None
        raw = None
        ts = None
        while pos<size-8:
            fh.seek(pos)
            blockType,blockSize = struct.unpack("II",fh.read(8))
            if blockSize <= 0:
                break # Corrupt!
            """
            try:
                blockName = MLV.BlockTypeLookup[blockType]
                print blockName,blockSize,pos,size,size-pos
            except:
                print "Unknown block type %08x"%blockType
                pass
            """
            if blockType==MLV.BlockType.FileHeader:
                header = self.parseFileHeader(fh,pos,blockSize)
            elif blockType==MLV.BlockType.RawInfo:
                raw = self.parseRawInfo(fh,pos,blockSize)
            elif blockType==MLV.BlockType.RealTimeClock:
                ts = self.parseRtc(fh,pos,blockSize)
            elif blockType==MLV.BlockType.VideoFrame:
                videoFrameHeader = self.parseVideoFrame(fh,pos,blockSize)
                framepos[videoFrameHeader[1]] = (fhi,pos,self.currentMetadata())
                pos += blockSize
                break # Only get first frame in this file
                #print videoFrameHeader[1],pos
            elif blockType==MLV.BlockType.Wavi:
                wavi = self.parseWavi(fh,pos,blockSize)
            elif blockType==MLV.BlockType.XREF:
                xref = self.parseXref(fh,pos,blockSize)
            elif blockType==MLV.BlockType.AudioFrame:
                audio = self.parseAudioFrame(fh,pos,blockSize)
            elif blockType==MLV.BlockType.Identity:
                self.identity = self.parseIdentity(fh,pos,blockSize)
            elif blockType==MLV.BlockType.LensInfo:
                lens = self.parseLens(fh,pos,blockSize)
            elif blockType==MLV.BlockType.ExposureInfo:
                expo = self.parseExpo(fh,pos,blockSize)
            elif blockType==MLV.BlockType.WhiteBalance:
                wbal = self.parseWbal(fh,pos,blockSize)
            count += 1
            pos += blockSize
            count += 1
        return header, raw, pos, size, ts
    def parseFileHeader(self,fh,pos,size):
        fh.seek(pos+8)
        headerData = fh.read(size-8)
        header = struct.unpack("<8cQHHIHHIIII",headerData[:44])
        """
        print "GUID:",header[8]
        print "fileNum:",header[9]
        print "fileCount:",header[10]
        print "fileFlags:",header[11]
        print "videoClass:",header[12]
        print "audioClass:",header[13]
        print "videoFrameCount:",header[14]
        print "audioFrameCount:",header[15]
        print "fpsNom:",header[16]
        print "fpsDenom:",header[17]
        print "fps:",float(header[16])/float(header[17])
        """
        return header
        #print "FileHeader:",self.header
    def parseRawInfo(self,fh,pos,size):
        fh.seek(pos+8)
        rawData = fh.read(size-8)
        raw = struct.unpack("<Q2H40i",rawData[:(8+2*2+40*4)])
        self.black = raw[10]
        self.white = raw[11]
        self.colorMatrix = colorMatrix(raw)
        self.cropOrigin = (raw[12],raw[13])
        self.cropSize = (raw[14],raw[15])
        self.activeArea = tuple(raw[16:20])
        #print "Crop origin:",self.cropOrigin
        #print "Crop size:",self.cropSize
        #print "Active area:",self.activeArea
        #print "Black level:", self.black,"White level:", self.white
        #print raw
        #print "RawInfo:",raw
        return raw
    def parseRtc(self,fh,pos,size):
        fh.seek(pos+8)
        rtcData = fh.read(size-8)
        rtc = struct.unpack("<Q10H8s",rtcData[:(8+10*2+8)])
        self.currentRtc = len(self.metadata)
        self.metadata.append(rtc)
        #print "Rtc:",rtc
        return rtc
    def parseIdentity(self,fh,pos,size):
        fh.seek(pos+8)
        idntData = fh.read(size-8)
        idnt = struct.unpack("<Q32sI32s",idntData[:(8+32+4+32)])
        makemodel = idnt[1].split('\0')[0]
        serial = idnt[3].split('\0')[0]
        make = "Canon"
        if makemodel.lower().startswith("canon "):
            model = makemodel[6:]
        elif makemodel.lower().startswith("failed"):
            # Workaround for TL-7D builds that couldn't get correct data
            model = "EOS 7D"
        else:
            model = "EOS"
        #print "Identity:",make,model,serial
        return make,model,serial,idnt
    def parseLens(self,fh,pos,size):
        fh.seek(pos+8)
        lensData = fh.read(size-8)
        lens = struct.unpack("<Q3HBBII32s32s",lensData[:(8+3*2+2+8+32+32)])
        name = lens[8].split('\0')[0]
        serial = lens[9].split('\0')[0]
        #print "Lens:",lens[:-2],name,serial
        self.currentLens = len(self.metadata)
        self.metadata.append((name,serial,lens[:-2]))
        return lens
    def parseExpo(self,fh,pos,size):
        fh.seek(pos+8)
        expoData = fh.read(size-8)
        expo = struct.unpack("<Q4IQ",expoData[:(8+4*4+8)])
        #print "Exposure:",expo
        self.currentExpo = len(self.metadata)
        self.metadata.append(expo)
        return expo
    def parseWbal(self,fh,pos,size):
        fh.seek(pos+8)
        wbalData = fh.read(size-8)
        wbal = struct.unpack("<Q7I",wbalData[:(8+7*4)])
        #print "WhiteBalance:",wbal
        self.currentWbal = len(self.metadata)
        self.metadata.append(wbal)
        return wbal
    def parseWavi(self,fh,pos,size):
        fh.seek(pos+8)
        waviData = fh.read(size-8)
        wavi = struct.unpack("<QHHIIHH",waviData[:(8+4+8+4)])
        name = self.filename[:-3]+"WAV"
        if self.allParsed: # Index already loaded
            if not os.path.exists(name): # File not found!
                self.allParsed = False
                print "Regenerating embedded WAV file"
            else:
                # Load it to check it contains frames
                self.wav = wave.open(name,'r')
                if self.wav.getnframes()==0:
                    self.wav.close()
                    self.wav = None
                    self.allParsed = False
                    print "Regenerating embedded WAV file"
                else:
                    self.wav.close()
                    self.wav = None
                    return wavi
        self.wav = wave.open(name,'w')
        self.wav.setparams((wavi[2],2,wavi[3],0,'NONE',''))
        #print "Wavi:",wavi,self.wav
        return wavi
    def parseXref(self,fh,pos,size):
        """
        The Xref info is not very useful for us since we still need to
        read all the chunks in order to find frame numbers
        """
        fh.seek(pos+8)
        xrefData = fh.read(size-8)
        offset = 8+4+4
        xref = struct.unpack("<QII",xrefData[:offset])
        xrefCount = xref[2]
        xrefs = []
        for x in range(xrefCount):
            xrefEntry = struct.unpack("<HHQ",xrefData[offset:offset+12])
            offset += 12
            #print xrefEntry
        #print "Xref:",xref
        return xref
    def parseVideoFrame(self,fh,pos,size):
        fh.seek(pos+8)
        rawData = fh.read(8+4+2+2+2+2+4+4)
        videoFrameHeader = struct.unpack("<QI4H2I",rawData)
        #print "Video frame",videoFrameHeader[1],"at",pos
        return videoFrameHeader
    def parseAudioFrame(self,fh,pos,size):
        fh.seek(pos+8)
        audioData = fh.read(8+4+4)
        audioFrameHeader = struct.unpack("<QII",audioData)
        #print "Audio frame",audioFrameHeader[1],"at",pos,audioFrameHeader,size-8-12
        #self.audioframepos[audioFrameHeader]
        audiodata = fh.read(size-24)
        #print "audio data",len(audiodata),self.wav
        if audioFrameHeader[0]<1 and audioFrameHeader[1]<1:
            pass # Workaround for bug in mlv_snd
        elif self.wav != None:
            #print "writing frames to wav"
            self.wav.writeframes(audiodata[audioFrameHeader[2]:])
        return audioFrameHeader
    def description(self):
        return self.filename
    def width(self):
        return self.raw[1]
    def height(self):
        return self.raw[2]
    def frames(self):
        return self.framecount
    def make(self):
        return self.identity[0]
    def model(self):
        return self.identity[1]
    def bodySerialNumber(self):
        return self.identity[2]
    def audioFrames(self):
        return self.audioFrameCount
    def nextUnindexedFile(self):
        for fileindex,info in enumerate(self.files):
            fhi, firstframe, frames, header, parsedTo, size = info
            if parsedTo < size:
                return fileindex,info
        self.allParsed = True
        return None
    def preindex(self):
        if not self.preindexing:
            return
        while 1:
            if self.allParsed:
                self.preindexing = False
                if self.wav:
                    self.wav.close()
                #print "Writing index"
                update = {"frameIndex_v1":self.framepos,"sequenceMetadata_v1":self.metadata}
                self.setMetaValues(update)
                #print "Index written"
                return
            preindexStep = 10
            indexinfo = self.nextUnindexedFile()
            if indexinfo == None:
                if len(self.framepos) < self.framecount:
                    print "Set indexed. Frames missing:",self.framecount - len(self.framepos)
                else:
                    pass
                    #print "Set indexed. No frames missing."
                return
            index,info = indexinfo
            fhi, firstframe, frames, header, pos, size = info
            fh = self.fhs[fhi]
            while (pos < size) and ((preindexStep > 0) or self.preloaderArgs.empty()):
                fh.seek(pos)
                blockType,blockSize = struct.unpack("II",fh.read(8))
                """
                try:
                    blockName = MLV.BlockTypeLookup[blockType]
                    print blockName,blockSize,pos,size,size-pos
                except:
                    print "Unknown block type %08x"%blockType
                    pass
                """

                if blockType==MLV.BlockType.VideoFrame:
                    videoFrameHeader = self.parseVideoFrame(fh,pos,blockSize)
                    self.framepos[videoFrameHeader[1]] = (fhi,pos,self.currentMetadata())
                    #print videoFrameHeader[1],pos
                    preindexStep -= 1
                elif blockType==MLV.BlockType.AudioFrame:
                    audioFrameHeader = self.parseAudioFrame(fh,pos,blockSize)
                elif blockType==MLV.BlockType.LensInfo:
                    lens = self.parseLens(fh,pos,blockSize)
                elif blockType==MLV.BlockType.ExposureInfo:
                    expo = self.parseExpo(fh,pos,blockSize)
                elif blockType==MLV.BlockType.RealTimeClock:
                    ts = self.parseRtc(fh,pos,blockSize)
                elif blockType==MLV.BlockType.WhiteBalance:
                    wbal = self.parseWbal(fh,pos,blockSize)
                pos += blockSize
                self.totalParsed += blockSize
            self.files[index] = (fhi, firstframe, frames, header, pos, size)
            if not self.preloaderArgs.empty():
                break

    def preloaderMain(self):
        #while self.preindexing:
        #    self.preindex() # Do some preindexing if still needed
        # Now we can load frames
        try:
            while 1:
                self.preindex() # Do some preindexing if still needed
                arg = self.preloaderArgs.get() # Will wait for a job
                if arg==None:
                    break
                try:
                    frame = self._loadframe(arg)
                except Exception,err:
                    print "Error reading frame %d, %s"%(arg,str(err))
                    traceback.print_exc()
                    frame = None
                self.preloaderResults.put((arg,frame))
        except:
            pass # Can happen if shutting down during preindexing
    def preloadFrame(self,index):
        self.initPreloader()
        self.preloaderArgs.put(index)
    def isPreloadedFrameAvailable(self):
        return not self.preloaderResults.empty()
    def nextFrame(self):
        return self.preloaderResults.get()
    def frame(self,index):
        preloadedindex = -1
        frame = None
        while preloadedindex!=index:
            preloadedindex,frame = self.preloaderResults.get()
            if preloadedindex==index:
                break
            self.preloadFrame(index)
        return frame
    def _getframedata(self,index,checkNextFile=True):
        printWhenFound = False
        try:
            fhi, framepos, metadata = self.framepos[index]
            return fhi, framepos, metadata
        except:
            # Do not have that frame (yet)
            # Find which file should contain that frame
            for fileindex,info in enumerate(self.files):
                fhi, firstframe, frames, header, parsedTo, size = info
                fh = self.fhs[fhi]
                if index>=firstframe and index<(firstframe+frames):
                    break
            # Parse through file until we find frame
            pos = parsedTo
            notFound = True
            while pos < size:
                fh.seek(pos)
                blockType,blockSize = struct.unpack("II",fh.read(8))
                """
                try:
                    blockName = MLV.BlockTypeLookup[blockType]
                    print blockName,blockSize,pos,size,size-pos
                except:
                    pass
                    print "Unknown block type:",blockType
                """
                #print blockName,blockSize
                if blockType==MLV.BlockType.VideoFrame:
                    videoFrameHeader = self.parseVideoFrame(fh,pos,blockSize)
                    self.framepos[videoFrameHeader[1]] = (fhi,pos,self.currentMetadata())
                    #print videoFrameHeader[1],index,fh,pos
                    if videoFrameHeader[1]==index:
                        pos += blockSize
                        notFound = False
                        break # Found it
                pos += blockSize
                if pos>=size and notFound:
                    self.files[fileindex] = (fhi, firstframe, frames, header, pos, size)
                    if checkNextFile:
                        # Update parsedTo point
                        # Try next file if there is one
                        print "FRAME NOT FOUND IN EXPECTED FILE",fileindex,index
                        printWhenFound = True
                        fileindex += 1
                        if fileindex<len(self.files):
                            #print "TRYING NEXT FILE"
                            fhi, firstframe, frames, header, parsedTo, size = self.files[fileindex]
                            fh = self.fhs[fhi]
                            pos = parsedTo
                    else:
                        print "FAILED TO FIND FRAME",index
                        return None
            # Update parsedTo point
            self.files[fileindex] = (fhi, firstframe, frames, header, pos, size)
            result = None
            try:
                result = self.framepos[index]
                if printWhenFound:
                    print "FOUND",index
            except:
                print "FAILED TO FIND FRAME AFTER SCAN",index
                self.framepos[index] = (None,None,None)
            return result
    def _loadframe(self,index,convert=True):
        fhframepos = self._getframedata(index)
        if fhframepos==None: # Return black frame
            return Frame(self,None,self.width(),self.height(),self.black,self.white)
        fhi,framepos,md = fhframepos
        if fhi==None: # Return black frame
            return Frame(self,None,self.width(),self.height(),self.black,self.white)
        fh = self.fhs[fhi]
        fh.seek(framepos)
        blockType,blockSize = struct.unpack("II",fh.read(8))
        videoFrameHeader = self.parseVideoFrame(fh,framepos,blockSize)
        rawstarts = framepos + 32 + videoFrameHeader[-2]
        rawsize = blockSize - 32 - videoFrameHeader[-2]
        fh.seek(rawstarts)
        PLOG(PLOG_CPU,"Reading frame %d size %d"%(index,rawsize))
        rawdata = fh.read(rawsize)
        PLOG(PLOG_CPU,"Read frame %d size %d"%(index,rawsize))
        mdkw = self.toMetadata(md)
        return Frame(self,rawdata,self.width(),self.height(),self.black,self.white,convert=convert,**mdkw)

class CDNG(ImageSequence):
    """
    Treat a directory of DNG files as sequential frames
    """
    def __init__(self,filename,preindex=False,**kwds):
        print "Opening CinemaDNG",filename
        self.filename = filename
        if os.path.isdir(filename):
            self.cdngpath = filename
        else:
            self.cdngpath = os.path.dirname(filename)
        self.dngs = [dng for dng in os.listdir(self.cdngpath) if dng.lower().endswith(".dng") and dng[0]!='.']
        self.dngs.sort()

        firstDngName = os.path.join(self.cdngpath,self.dngs[0])
        self.firstDng = fd = DNG.DNG()
        fd.readFile(firstDngName) # Only parse metadata

        self.fpsnum = 25000
        self.fpsden = 1000
        self.fps = 25.0
        FrameRate = self.tag(fd,DNG.Tag.FrameRate)
        if FrameRate != None:
            FrameRate = FrameRate[3][0]
            self.fps = float(FrameRate[0])/float(FrameRate[1])
            self.fpsnum = FrameRate[0]
            self.fpsden = FrameRate[1]
            print "FPS:",self.fps,FrameRate
        else:
            print "No internal frame rate. Defaulting to",self.fps

        self.black = fd.FULL_IFD.tags[DNG.Tag.BlackLevel[0]][3][0]
        self.white = fd.FULL_IFD.tags[DNG.Tag.WhiteLevel[0]][3][0]
        matrix = self.tag(fd,DNG.Tag.ColorMatrix1)
        self.colormatrix = np.eye(3)
        if matrix != None:
            self.colorMatrix = np.matrix(np.array([float(n)/float(d) for n,d in matrix[3]]).reshape(3,3))

        baselineExposure = 0.0 # EV
        if DNG.Tag.BaselineExposure[0] in fd.FULL_IFD.tags:
            n,d = fd.FULL_IFD.tags[DNG.Tag.BaselineExposure[0]][3][0]
            baselineExposure = float(n)/float(d)
        if DNG.Tag.BaselineExposureOffset[0] in fd.FULL_IFD.tags:
            n,d = fd.FULL_IFD.tags[DNG.Tag.BaselineExposureOffset[0]][3][0]
            baselineExposureOffset = float(n)/float(d)
            baselineExposure += baselineExposureOffset
        self.brightness = math.pow(2.0,baselineExposure)
        print "brightness",self.brightness

        #print "color matrix:",self.colorMatrix
        #self.colorMatrix = colorMatrix(self.info)
        print "Black level:", self.black, "White level:", self.white

        self._width = fd.FULL_IFD.width
        self._height = fd.FULL_IFD.length

        bps = self.bitsPerSample = fd.FULL_IFD.tags[DNG.Tag.BitsPerSample[0]][3][0]
        print "BitsPerSample:",bps
        if bps != 14 and bps != 16:
            print "Unsupported BitsPerSample = ",bps,"(should be 14 or 16)"
            raise IOError # Only support 14 or 16 bitsPerSample

        neutral = self.tag(fd,DNG.Tag.AsShotNeutral)
        self.whiteBalance = [1.0,1.0,1.0]
        if neutral:
            self.whiteBalance = [float(d)/float(n) for n,d in neutral[3]] # Note: immediately take reciprocal
            print "rgb",self.whiteBalance
        #self.whiteBalance =

        self._make = "Unknown Make"
        self._model = "Unknown Model"
        try:
            self._make = fd.FULL_IFD.tags[DNG.Tag.Make[0]][3].lstrip().strip('\0')
            self._model = fd.FULL_IFD.tags[DNG.Tag.Model[0]][3].lstrip().strip('\0')
            if self._model.startswith(self._make):
                self._model = self._model[len(self._make):].lstrip()
        except:
            pass

        self.cropOrigin = (0,0)
        self.cropSize = (self._width,self._height)
        self.activeArea = (0,0,self._height,self._width) # Y,X,Y,X
        if DNG.Tag.DefaultCropOrigin[0] in fd.FULL_IFD.tags:
            print fd.FULL_IFD.tags[DNG.Tag.DefaultCropOrigin[0]][3]
            self.cropOrigin = tuple(fd.FULL_IFD.tags[DNG.Tag.DefaultCropOrigin[0]][3])
        if DNG.Tag.DefaultCropSize[0] in fd.FULL_IFD.tags:
            print fd.FULL_IFD.tags[DNG.Tag.DefaultCropSize[0]][3]
            self.cropSize = tuple(fd.FULL_IFD.tags[DNG.Tag.DefaultCropSize[0]][3])
        if DNG.Tag.ActiveArea[0] in fd.FULL_IFD.tags:
            print fd.FULL_IFD.tags[DNG.Tag.ActiveArea[0]][3]
            self.activeArea = tuple(fd.FULL_IFD.tags[DNG.Tag.ActiveArea[0]][3])
        print "Crop origin:",self.cropOrigin
        print "Crop size:",self.cropSize
        print "Active area:",self.activeArea

        self.firstFrame = self._loadframe(0,convert=False)

        self.preloader = threading.Thread(target=self.preloaderMain)
        self.preloaderArgs = Queue.Queue(2)
        self.preloaderResults = Queue.Queue(2)
        self.preloader.daemon = True
        self.preloader.start()
        super(CDNG,self).__init__(userMetadataFilename=ImageSequence.userMetadataNameFromOriginal(firstDngName),**kwds)
    def tag(self,dng,tag):
        if tag[0] in dng.FULL_IFD.tags: return dng.FULL_IFD.tags[tag[0]]
        elif tag[0] in dng.THUMB_IFD.tags: return dng.THUMB_IFD.tags[tag[0]]
        else: return None

    def description(self):
        firstName = self.dngs[0]
        lastName = self.dngs[-1]
        name,ext = os.path.splitext(firstName)
        lastname,ext = os.path.splitext(lastName)
        return os.path.join(self.cdngpath,"["+name+"-"+lastname+"]"+ext)

    def close(self):
        self.preloaderArgs.put(None) # So that preloader thread exits
        self.preloader.join() # Wait for it to finish
        self.firstDng.close()
    def indexingStatus(self):
        return 1.0
    def width(self):
        return self._width
    def height(self):
        return self._height
    def frames(self):
        return len(self.dngs)
    def make(self):
        return self._make
    def model(self):
        return self._model
    def bodySerialNumber(self):
        return self.identity[2]
    def audioFrames(self):
        return 0
    def preloaderMain(self):
        while 1:
            arg = self.preloaderArgs.get() # Will wait for a job
            if arg==None:
                break
            frame = self._loadframe(arg)
            self.preloaderResults.put((arg,frame))
    def preloadFrame(self,index):
        self.preloaderArgs.put(index)
    def isPreloadedFrameAvailable(self):
        return not self.preloaderResults.empty()
    def nextFrame(self):
        return self.preloaderResults.get()
    def frame(self,index):
        preloadedindex = -1
        frame = None
        while preloadedindex!=index:
            preloadedindex,frame = self.preloaderResults.get()
            if preloadedindex==index:
                break
            self.preloadFrame(index)
        return frame
    def _loadframe(self,index,convert=True):
        if index>=0 and index<self.frames():
            filename = self.dngs[index]
            dng = DNG.DNG()
            dng.readFileIn(os.path.join(self.cdngpath,filename))
            rawdata = dng.FULL_IFD.stripsCombined()
            dng.close()
            return Frame(self,rawdata,self.width(),self.height(),self.black,self.white,byteSwap=1,bitsPerSample=self.bitsPerSample,convert=convert)
        return ""

class TIFFSEQ(ImageSequence):
    """
    Treat a directory of (e.g. 16bit) TIFF files as sequential frames
    """
    def __init__(self,filename,preindex=False,**kwds):
        print "Opening TIFF sequence",filename
        self.filename = filename
        if os.path.isdir(filename):
            self.path = filename
        else:
            self.path = os.path.dirname(filename)
        self.tiffs = [tiff for tiff in os.listdir(self.path) if (tiff.lower().endswith(".tif") or tiff.lower().endswith(".tiff")) and tiff[0]!='.']
        self.tiffs.sort()

        firstName = os.path.join(self.path,self.tiffs[0])
        self.firstTiff = fd = DNG.DNG()
        fd.readFile(firstName) # Only parse metadata

        self.fps = 25.0 # Hardcoded to 25
        self.fpsnum = 25000
        self.fpsden = 1000
        print "Assumed FPS:",self.fps

        self.black = 0
        self.white = 65535
        self.colorMatrix = np.matrix(np.eye(3))
        self.whiteBalance = None
        self.brightness = 1.0
        print "Black level:", self.black, "White level:", self.white

        self._width = fd.ifds[0].width
        self._height = fd.ifds[0].length
        self.cropOrigin = (0,0)
        self.cropSize = (self._width,self._height)
        self.activeArea = (0,0,self._height,self._width)

        bps = self.bitsPerSample = fd.ifds[0].tags[DNG.Tag.BitsPerSample[0]][3][0]
        print "BitsPerSample:",bps
        if bps != 16:
            print "Unsupported BitsPerSample = ",bps,"(should be 16)"
            raise IOError # Only support 16 bitsPerSample

        self.firstFrame = self._loadframe(0,convert=False)

        self.preloader = threading.Thread(target=self.preloaderMain)
        self.preloaderArgs = Queue.Queue(2)
        self.preloaderResults = Queue.Queue(2)
        self.preloader.daemon = True
        self.preloader.start()
        super(TIFFSEQ,self).__init__(userMetadataFilename=ImageSequence.userMetadataNameFromOriginal(firstName),**kwds)
    def description(self):
        firstName = self.tiffs[0]
        lastName = self.tiffs[-1]
        name,ext = os.path.splitext(firstName)
        lastname,ext = os.path.splitext(lastName)
        return os.path.join(self.path,"["+name+"-"+lastname+"]"+ext)

    def close(self):
        self.preloaderArgs.put(None) # So that preloader thread exits
        self.preloader.join() # Wait for it to finish
        self.firstTiff.close()
    def indexingStatus(self):
        return 1.0
    def width(self):
        return self._width
    def height(self):
        return self._height
    def frames(self):
        return len(self.tiffs)
    def audioFrames(self):
        return 0
    def preloaderMain(self):
        while 1:
            arg = self.preloaderArgs.get() # Will wait for a job
            if arg==None:
                break
            frame = self._loadframe(arg)
            self.preloaderResults.put((arg,frame))
    def preloadFrame(self,index):
        self.preloaderArgs.put(index)
    def isPreloadedFrameAvailable(self):
        return not self.preloaderResults.empty()
    def nextFrame(self):
        return self.preloaderResults.get()
    def frame(self,index):
        preloadedindex = -1
        frame = None
        while preloadedindex!=index:
            preloadedindex,frame = self.preloaderResults.get()
            if preloadedindex==index:
                break
            self.preloadFrame(index)
        return frame
    def _loadframe(self,index,convert=True):
        if index>=0 and index<self.frames():
            filename = self.tiffs[index]
            tiff = DNG.DNG()
            tiff.readFileIn(os.path.join(self.path,filename))
            try:
                rawdata = tiff.ifds[0].stripsCombined()
            except:
                import traceback
                traceback.print_exc()
                print "Error fetching data from",filename
                rawdata = np.zeros((self.width()*self.height()*3,),dtype=np.uint16).tostring()
            tiff.close()
            return Frame(self,rawdata,self.width(),self.height(),self.black,self.white,byteSwap=1,bitsPerSample=self.bitsPerSample,bayer=False,rgb=True,convert=convert)
        return ""

def loadRAWorMLV(filename,preindex=True):
    fl = filename.lower()
    if fl.endswith(".raw"):
        return MLRAW(filename,preindex)
    elif fl.endswith(".mlv"):
        return MLV(filename,preindex)
    elif fl.endswith(".dng"):
        return CDNG(os.path.dirname(filename),preindex)
    elif fl.endswith(".tif") or fl.endswith(".tiff"):
        return TIFFSEQ(os.path.dirname(filename),preindex)
    elif os.path.isdir(filename):
        filenames = os.listdir(filename)
        dngfiles = [dng for dng in filenames if dng.lower().endswith(".dng")]
        tifffiles = [tiff for tiff in filenames if tiff.lower().endswith(".tif") or tiff.lower().endswith(".tiff")]
        if len(dngfiles)>0:
            return CDNG(filename,preindex)
        elif len(tifffiles)>0:
            return TIFFSEQ(filename,preindex)
    return None

