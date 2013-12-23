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
import sys,struct,os,math,time,threading,Queue,traceback

haveDemosaic = False

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
    if ("__version__" not in dir(bitunpack)) or bitunpack.__version__!="1.4":
        print """

!!! Wrong version of bitunpack found !!!
!!! Please rebuild latest version. !!!

"""
        raise
    def unpacks14np16(rawdata,width,height):
        unpacked,stats = bitunpack.unpack14to16(rawdata)
        return np.frombuffer(unpacked,dtype=np.uint16),stats
    def demosaic14(rawdata,width,height,black):
        raw = bitunpack.demosaic14(rawdata,width,height,black)
        return np.frombuffer(raw,dtype=np.float32)
    haveDemosaic = True
except:
    print """Falling back to Numpy for bit unpacking operations.
Consider compiling bitunpack module for faster conversion and export."""
    def unpacks14np16(rawdata,width,height):
        pixels = width*height
        packed = pixels/8.0*7.0
        rawzero = np.fromstring(rawdata,dtype=np.uint16)
        packing = rawzero[:packed].reshape((packed/7.0,7))
        unpacked = np.zeros((pixels/8,8),dtype=np.uint16)
        packing0 = packing[:,0]
        packing1 = packing[:,1]
        packing2 = packing[:,2]
        packing3 = packing[:,3]
        packing4 = packing[:,4]
        packing5 = packing[:,5]
        packing6 = packing[:,6]
        unpacked[:,0] = packing0>>2
        unpacked[:,1] = (packing1>>4)|((packing0&0x3)<<12)
        unpacked[:,2] = packing2>>6|(np.bitwise_and(packing1,0xF)<<10)
        unpacked[:,3] = packing3>>8|(np.bitwise_and(packing2,0x3F)<<8)
        unpacked[:,4] = packing4>>10|(np.bitwise_and(packing3,0xFF)<<6)
        unpacked[:,5] = packing5>>12|(np.bitwise_and(packing4,0x3FF)<<4)
        unpacked[:,6] = packing6>>14|(np.bitwise_and(packing5,0xFFF)<<2)
        unpacked[:,7] = packing6&0x3FFF
        stats = (np.min(unpacked),np.max(unpacked))
        return unpacked,stats
    def demosaic14(rawdata,width,height,black):
        # No numpy implementation
        return np.zeros(shape=(width*height,),dtype=np.float32)

class Frame:
    def __init__(self,rawfile,rawdata,width,height,black):
        global haveDemosaic
        #print "opening frame",len(rawdata),width,height
        #print width*height
        self.rawfile = rawfile
        self.black = black
        self.rawdata = rawdata
        self.width = width
        self.height = height
        self.rawdata = rawdata
        self.canDemosaic = haveDemosaic
    def convert(self):
        if self.rawdata != None:
            self.rawimage,self.framestats = unpacks14np16(self.rawdata,self.width,self.height)
        else:
            rawimage = np.empty(self.width*self.height,dtype=np.uint16)
            rawimage.fill(self.black)
            self.rawimage = rawimage.tostring()
    def demosaic(self):
        # CPU based demosaic -> SLOW!
        if self.rawdata != None:
            self.rgbimage = demosaic14(self.rawdata,self.width,self.height,self.black)
        else:
            self.rgbimage = np.zeros(self.width*self.height*3,dtype=np.uint16).tostring()


def colorMatrix(raw_info):
    vals = np.array(raw_info[-19:-1]).astype(np.float32)
    nom = vals[::2]
    denom = vals[1::2]
    scaled = (nom/denom).reshape((3,3))
    camToXYZ = np.matrix(scaled).getI()
    XYZtosRGB = np.matrix([[3.2404542,-1.5371385,-0.4985314],
                           [-0.9692660,1.8760108,0.0415560],
                           [0.0556434,-0.2040259,1.0572252]])
    camToLinearsRGB = XYZtosRGB * camToXYZ
    #print "colorMatrix:",camTosRGB
    return camToLinearsRGB

def getRawFileSeries(basename):
    dirname,filename = os.path.split(basename)
    base = filename[:-2]
    samenamefiles = [n for n in os.listdir(dirname) if n[:-2]==base and n!=filename]
    allfiles = [filename]
    samenamefiles.sort()
    allfiles.extend(samenamefiles)
    return dirname,allfiles
"""
ML RAW - need to handle spanning files
"""
class MLRAW:
    def __init__(self,filename):
        print "Opening MLRAW file",filename
        dirname,allfiles = getRawFileSeries(filename)
        indexfile = os.path.join(dirname,allfiles[-1])
        self.indexfile = file(indexfile,'rb')
        self.indexfile.seek(-192,os.SEEK_END)
        footerdata = self.indexfile.read(192)
        self.footer = struct.unpack("4shhiiiiii",footerdata[:8*4])
        self.fps = float(self.footer[6])*0.001
        print "FPS:",self.fps
        self.info = struct.unpack("40i",footerdata[8*4:])
        #print self.footer,self.info
        self.black = self.info[7]
        self.white = self.info[8]
        self.colorMatrix = colorMatrix(self.info)
        print "Black level:", self.black, "White level:", self.white
        self.framefiles = []
        for framefilename in allfiles:
            fullframefilename = os.path.join(dirname,framefilename)
            framefile = file(fullframefilename,'rb')
            framefile.seek(0,os.SEEK_END)
            framefilelen = framefile.tell()
            self.framefiles.append((framefile,framefilelen))
        self.preloader = threading.Thread(target=self.preloaderMain) 
        self.preloaderArgs = Queue.Queue(1)
        self.preloaderResults = Queue.Queue(1)
        self.preloader.daemon = True
        self.preloader.start()
    def close():
        self.indexfile.close()
        for filehandle,filelen in self.framefiles:
            filehandle.close()
    def width(self):
        return self.footer[1]
    def height(self):
        return self.footer[2]
    def frames(self):
        return self.footer[4]
    def audioFrames(self):
        return 0
    def preloaderMain(self):
        while 1:
            arg = self.preloaderArgs.get() # Will wait for a job
            frame = self._loadframe(arg)
            self.preloaderResults.put((arg,frame))
    def preloadFrame(self,index):
        self.preloaderArgs.put(index)
    def frame(self,index):
        preloadedindex = -1
        frame = None
        while preloadedindex!=index:
            preloadedindex,frame = self.preloaderResults.get() 
            if preloadedindex==index:
                break
            self.preloadFrame(index)
        return frame
    def _loadframe(self,index):
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
                newframedata = filehandle.read(needfromfile)
                needed -= len(newframedata)
                framedata += newframedata
                if needed==0:
                    break
            return Frame(self,framedata,self.width(),self.height(),self.black)
        return ""

 
"""
ML MLV format - need to handle spanning files
"""
class MLV:
    class BlockType:
        FileHeader = 0x49564c4d
        VideoFrame = 0x46444956
        Audio = 0x46445541
        RawInfo = 0x49574152
        WavInfo = 0x73866587
        ExposureInfo = 0x4f505845
        LensInfo = 0x534e454c
        RealTimeClock = 0x49435452
        Idendity = 0x544e4449
        XREF = 0x70698288
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

    def __init__(self,filename):
        print "Opening MLV file",filename
        dirname,allfiles = getRawFileSeries(filename)
        mlvfile = file(filename,'rb')
        self.framepos = {}
        self.audioframepos = {}
        header,raw,parsedTo,size,ts = self.parseFile(mlvfile,self.framepos)
        self.fps = float(header[16])/float(header[17])
        print "FPS:",self.fps
        self.framecount = header[14]
        self.audioFrameCount = header[15]
        self.preindexed = 0
        self.header = header
        self.raw = raw
        self.ts = ts
        self.files = [(mlvfile,0,header[14],header,parsedTo, size)]
        for spanfilename in allfiles[1:]:
            fullspanfile = os.path.join(dirname,spanfilename)
            spanfile = file(fullspanfile,'rb')
            header,raw,parsedTo,size,ts = self.parseFile(spanfile,self.framepos)
            self.files.append((spanfile,self.framecount,header[14],header,parsedTo, size))
            self.framecount += header[14]
            self.audioFrameCount += header[15]
        self.preloader = None
        self.allParsed = False
        print "Audio frame count",self.audioFrameCount
    def initPreloader(self):
        if (self.preloader == None):
            self.preloader = threading.Thread(target=self.preloaderMain) 
            self.preloaderArgs = Queue.Queue(1)
            self.preloaderResults = Queue.Queue(1)
            self.preloader.daemon = True
            self.preloader.start()
    def close(self):
        for fh,firstframe,frames,header,parsedTo,size in self.files:
            fh.close()
    def parseFile(self,fh,framepos):
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
            """
            try:
                blockName = MLV.BlockTypeLookup[blockType]
                print blockName,blockSize,pos,size,size-pos
            except:
                pass
                print "Unknown block type %08x"%blockType
            """
            if blockType==MLV.BlockType.FileHeader:
                header = self.parseFileHeader(fh,pos,blockSize)
            elif blockType==MLV.BlockType.RawInfo:
                raw = self.parseRawInfo(fh,pos,blockSize)
            elif blockType==MLV.BlockType.RealTimeClock:
                ts = self.parseRtc(fh,pos,blockSize)
            elif blockType==MLV.BlockType.VideoFrame:
                videoFrameHeader = self.parseVideoFrame(fh,pos,blockSize)
                framepos[videoFrameHeader[1]] = (fh,pos)
                pos += blockSize
                break # Only get first frame in this file
                #print videoFrameHeader[1],pos
            elif blockType==MLV.BlockType.Wavi:
                wavi = self.parseWavi(fh,pos,blockSize)
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
        print "Black level:", self.black,"White level:", self.white
        #print raw
        return raw
        #print "RawInfo:",self.raw
    def parseRtc(self,fh,pos,size):
        fh.seek(pos+8)
        rtcData = fh.read(size-8)
        rtc = struct.unpack("<Q10H8s",rtcData[:(8+10*2+8)])
        return rtc
        #print "RawInfo:",self.raw
    def parseWavi(self,fh,pos,size):
        fh.seek(pos+8)
        waviData = fh.read(size-8)
        wavi = struct.unpack("<QHHIIHH",waviData[:(8+4+8+4)])
        print "Wavi:",wavi
        return wavi
    def parseVideoFrame(self,fh,pos,size):
        fh.seek(pos+8)
        rawData = fh.read(8+4+2+2+2+2+4+4)
        videoFrameHeader = struct.unpack("<QI4H2I",rawData)
        #print "VideoFrame:",videoFrameHeader
        return videoFrameHeader
    def width(self):
        return self.raw[1]
    def height(self):
        return self.raw[2]
    def frames(self):
        return self.framecount
    def audioFrames(self):
        return self.audioFrameCount
    def nextUnindexedFile(self):
        for fileindex,info in enumerate(self.files):
            fh, firstframe, frames, header, parsedTo, size = info
            if parsedTo < size:
                return fileindex,info
        self.allParsed = True
        return None
    def preindex(self):
        if self.allParsed:
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
        fh, firstframe, frames, header, pos, size = info
        while (pos < size) and (preindexStep > 0):
            fh.seek(pos)
            blockType,blockSize = struct.unpack("II",fh.read(8))
            """
            try:
                blockName = MLV.BlockTypeLookup[blockType]
                print blockName,blockSize,pos,size,size-pos
            except:
                pass
                print "Unknown block type %08x"%blockType
            """
            if blockType==MLV.BlockType.VideoFrame:
                videoFrameHeader = self.parseVideoFrame(fh,pos,blockSize)
                self.framepos[videoFrameHeader[1]] = (fh,pos)
                #print videoFrameHeader[1],pos
                preindexStep -= 1
            pos += blockSize
        self.files[index] = (fh, firstframe, frames, header, pos, size)

    def preloaderMain(self):
        while 1:
            self.preindex() # Do some preindexing if still needed
            arg = self.preloaderArgs.get() # Will wait for a job
            try:
                frame = self._loadframe(arg)
            except Exception,err:
                print "Error reading frame %d, %s"%(arg,str(err))
                traceback.print_exc()
                frame = None
            self.preloaderResults.put((arg,frame))
    def preloadFrame(self,index):
        self.initPreloader()
        self.preloaderArgs.put(index)
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
            fh, framepos = self.framepos[index]
            return fh, framepos
        except:
            # Do not have that frame (yet)
            # Find which file should contain that frame
            for fileindex,info in enumerate(self.files):
                fh, firstframe, frames, header, parsedTo, size = info
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
                    self.framepos[videoFrameHeader[1]] = (fh,pos)
                    #print videoFrameHeader[1],index,fh,pos
                    if videoFrameHeader[1]==index:
                        pos += blockSize
                        notFound = False
                        break # Found it
                pos += blockSize
                if pos>=size and notFound:
                    self.files[fileindex] = (fh, firstframe, frames, header, pos, size)
                    if checkNextFile:
                        # Update parsedTo point
                        # Try next file if there is one
                        print "FRAME NOT FOUND IN EXPECTED FILE",fileindex,index
                        printWhenFound = True
                        fileindex += 1
                        if fileindex<len(self.files):
                            #print "TRYING NEXT FILE"
                            fh, firstframe, frames, header, parsedTo, size = self.files[fileindex]
                            pos = parsedTo
                    else:
                        print "FAILED TO FIND FRAME",index
                        return None
            # Update parsedTo point
            self.files[fileindex] = (fh, firstframe, frames, header, pos, size)
            result = None
            try:
                result = self.framepos[index]
                if printWhenFound:
                    print "FOUND",index
            except:
                print "FAILED TO FIND FRAME AFTER SCAN",index
                self.framepos[index] = (None,None)
            return result
    def _loadframe(self,index):
        fhframepos = self._getframedata(index)
        if fhframepos==None: # Return black frame
            return Frame(self,None,self.width(),self.height(),self.black)
        fh,framepos = fhframepos
        if fh==None: # Return black frame
            return Frame(self,None,self.width(),self.height(),self.black)
        fh.seek(framepos)
        blockType,blockSize = struct.unpack("II",fh.read(8))
        videoFrameHeader = self.parseVideoFrame(fh,framepos,blockSize)
        rawstarts = framepos + 32 + videoFrameHeader[-2]
        rawsize = blockSize - 32 - videoFrameHeader[-2]
        fh.seek(rawstarts)
        rawdata = fh.read(rawsize)
        return Frame(self,rawdata,self.width(),self.height(),self.black)

def loadRAWorMLV(filename):
    fl = filename.lower()
    if fl.endswith(".raw"):
        return MLRAW(filename)
    elif fl.endswith(".mlv"):
        return MLV(filename)

