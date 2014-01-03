#!/usr/bin/python2.7
"""
DNG.py
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

Logic to read and write DNG/CDNG file sets
"""

# standard python imports
import sys,struct,os,math,time,threading,Queue,traceback,wave

class Type:
    # TIFF Type Format = (Tag TYPE value, Size in bytes of one instance)
    Invalid = (0,0) # Should not be used
    Byte = (1,1) # 8-bit unsigned
    Ascii = (2,1) # 7-bit ASCII code
    Short = (3,2) # 16-bit unsigned
    Long = (4,4) # 32-bit unsigned
    Rational = (5,8) # 2 Longs, numerator:denominator
    Sbyte = (6,1) # 8 bit signed integer
    Undefined = (7,1) # 8 bit byte containing anything
    Sshort = (8,2) # 16 bit signed
    Slong = (9,4) # 32 bit signed
    Srational = (10,8) # 2 Slongs, numerator:denominator
    Float = (11,4) # 32bit float IEEE
    Double = (12,8) # 64bit double IEEE
    IFD = (13,4) # IFD (Same as Long)

Types = [(getattr(Type,n),n) for n in dir(Type) if n!="__doc__" and n!="__module__"]
Types.sort()

class Tag:
    # TIFF/DNG/EXIF/CinemaDNG Tag Format = (TAG value, Tag Type)
    NewSubfileType = (254,Type.Long)
    ImageWidth = (256,Type.Long)
    ImageLength = (257,Type.Long)
    BitsPerSample = (258,Type.Short)
    Compression = (259,Type.Short)
    PhotometricInterpretation = (262,Type.Short)
    ImageDescription = (270,Type.Ascii)
    Make = (271,Type.Ascii)
    Model = (272,Type.Ascii)
    StripOffsets = (273,Type.Long)
    Orientation = (274,Type.Short)
    SamplesPerPixel = (277,Type.Short)
    RowsPerStrip = (278,Type.Short)
    StripByteCounts = (279,Type.Long)
    XResolution = (282,Type.Rational)
    YResolution = (283,Type.Rational)
    PlanarConfiguration = (284,Type.Short)
    ResolutionUnit = (296,Type.Short)
    Software = (305,Type.Ascii)
    DateTime = (306,Type.Ascii)
    Artist = (315,Type.Ascii)
    SubIFD = (330,Type.Long)
    CFARepeatPatternDim = (33421,Type.Short)
    CFAPattern = (33422,Type.Byte)
    Copyright = (33432,Type.Ascii)
    ExposureTime = (33434,Type.Rational)
    FNumber = (33437,Type.Rational)
    EXIF_IFD = (34665,Type.Long)
    ExposureProgram = (34850,Type.Short)
    PhotographicSensitivity = (34855,Type.Short)
    ExifVersion = (36864,Type.Undefined)
    DateTimeOriginal = (36867,Type.Ascii)
    ShutterSpeedValue = (37377,Type.Srational)
    ApertureValue = (37378,Type.Rational)
    ExposureBiasValue = (37380,Type.Srational)
    MaxApertureValue = (37381,Type.Rational)
    MeteringMode = (37383,Type.Short)
    Flash = (37385,Type.Short)
    FocalLength = (37386,Type.Rational)
    TIFF_EP_StandardID = (37398,Type.Byte)
    SubsecTime = (37520,Type.Ascii)
    SubsecTimeOriginal = (37521,Type.Ascii)
    FocalLengthIn35mmFilm = (41989,Type.Short)
    EXIFPhotoBodySerialNumber = (42033,Type.Ascii)
    EXIFPhotoLensModel = (42036,Type.Ascii)
    DNGVersion = (50706,Type.Byte)
    DNGBackwardVersion = (50707,Type.Byte)
    UniqueCameraModel = (50708,Type.Ascii)
    BlackLevel = (50714,Type.Long)
    WhiteLevel = (50717,Type.Long)
    DefaultCropOrigin = (50719,Type.Long)
    DefaultCropSize = (50720,Type.Long)
    ColorMatrix1 = (50721,Type.Srational)
    AnalogBalance = (50727,Type.Rational)
    AsShotNeutral = (50728,Type.Rational)
    BaselineExposure = (50730,Type.Srational)
    BaselineNoise = (50731,Type.Rational)
    BaselineSharpness = (50732,Type.Rational)
    LinearResponseLimit = (50734,Type.Rational)
    CalibrationIlluminant1 = (50778,Type.Short)
    CalibrationIlluminant2 = (50779,Type.Short)
    ActiveArea = (50829,Type.Long)
    FrameRate = (51044,Type.Srational)
    OpcodeList1 = (51008,Type.Undefined)

IfdNames = [n for n in dir(Tag) if n!="__doc__" and n!="__module__"]
IfdValues = [getattr(Tag,n) for n in IfdNames]
IfdIdentifiers = [getattr(Tag,n)[0] for n in IfdNames]
IfdTypes = [getattr(Tag,n)[1][0] for n in IfdNames]
IfdLookup = dict(zip(IfdIdentifiers,IfdNames))

class DNG(object):

    def __init__(self,log=False,parse=True): 
        self.log = log
        self.autoparse = parse
        self.df = None # File
        self.dd = None # Buffer
        self.FULL_IFD = None
        self.THUMB_IFD = None

    def readFile(self,filename):
        """
        Read from file system the structure of the given file
        Will not read image data from file system
        Better if only metadata needed with minimum data read
        """
        df = self.df = file(filename,'rb')
        df.seek(0,os.SEEK_END)
        l = self.dfl = df.tell()
        self.dp = 0
        df.seek(self.dp)
        if self.log: print "DNG file",filename,"length",l
        if self.autoparse: self.parse()

    def readFileIn(self,filename):
        """
        Read entire file from file system 
        Only 1 large file read operation
        """
        df = file(filename,'rb')
        self.dd = df.read()
        df.close()
        if self.log: print "DNG file",filename,"length",len(self.dd)
        if self.autoparse: self.parse()

    def parse(self):
        self.ifds = []
        ifdOffset = self.readHeader()
        while ifdOffset != 0:
            ifd,ifdOffset = self.readIfd(ifdOffset)
            self.ifds.append(ifd)

    def readFrom(self,offset,length):
        if self.df:
            if (offset+length)>self.dfl:
                raise EOFError
            if offset != self.dp:
                self.dp = offset
            self.df.seek(self.dp)
            data = self.df.read(length)
            self.dp += len(data)
            return data
        elif self.dd:
            if (offset+length)>len(self.dd):
                raise EOFError
            return self.dd[offset:offset+length]

    def close(self):
        if self.df:
            self.df.close()
            self.df = None
        elif self.dd:
            self.dd = None

    def readHeader(self):
        h = self.readFrom(0,8)
        byteOrder = struct.unpack("<H",h[:2])[0]
        if byteOrder == 0x4949: # Little endian
            if self.log: print "Little endian"
            self.bo = "<"
        elif byteOrder == 0x4D4d: # Big endian
            if self.log: print "Big endian"
            self.bo = ">"
        valid,firstIfdOffset = struct.unpack(self.bo+"HI",h[2:])
        if valid != 42:
            raise IOError
        return firstIfdOffset

    class IFD(object):
        def __init__(self,dng):
            self.dng = dng
            self.entries = []
            self.tags = {}
            self.subIFDs = []
            self.subFileType = None
            self.EXIF_IFD = None
            self.width = None
            self.length = None
            self.RowsPerStrip = None
            self.PlanarConfiguration = None
        def subFileType(self):  
            t = self.subFileType
            if t&1: 
                if self.log: print "ReducedResolution"
            if t&1==0:
                if self.log: print "FullResolution"
            if t&2:
                if self.log: print "PartOfMultipage"
            if t&4:
                if self.log: print "TransparencyMask"
            return t
        def isFull(self):
            return self.subFileType&1==0
        def isThumb(self):
            return self.subFileType&1==1
        def strips(self):
            if not self.RowsPerStrip: raise IOError
            if not self.length: raise IOError
            if not self.PlanarConfiguration: raise IOError
            if self.PlanarConfiguration != 1:
                if self.log: print "Unsupported PlanarConfiguration = ",self.PlanarConfiguration
                raise IOError
            StripsPerImage = self.RowsPerStrip * self.length
            StripByteCounts = self.tags[Tag.StripByteCounts[0]][3]
            StripOffsets = self.tags[Tag.StripOffsets[0]][3]
            s = []
            for byteCount,offset in zip(StripByteCounts,StripOffsets):
                strip = self.dng.readFrom(offset,byteCount)
                s.append(strip)
            return s
        def stripsCombined(self):
            s = self.strips()
            if len(s)==1:
                return s[0]
            else:
                return ''.join(s)

    def readIfd(self,offset):
        count = struct.unpack(self.bo+"H",self.readFrom(offset,2))[0]
        if self.log: print "IFD entries:",count
        ifdEntryData = self.readFrom(offset+2,count*12+4)
        ifdFormat = self.bo + "HHII"
        ifd = DNG.IFD(self)
        for i in range(count):
            ifdEntry = struct.unpack(ifdFormat,ifdEntryData[i*12:i*12+12])
            fullIfdEntry = self.readIfdEntry(ifd,ifdEntry,ifdEntryData[i*12+8:i*12+12])
            ifd.entries.append(fullIfdEntry)
            ifd.tags[fullIfdEntry[0]] = fullIfdEntry
        nextOffset = struct.unpack(self.bo+"I",ifdEntryData[-4:])[0]
        return ifd,nextOffset

    def decodeTagData(self,itype,icount,data):
        if itype==Type.Invalid[0]:
            raise IOError
        elif itype==Type.Byte[0]:
            return struct.unpack("<"+"%dB"%icount,data[:icount])
        elif itype==Type.Ascii[0]:
            return struct.unpack("<"+"%ds"%icount,data[:icount])[0]
        elif itype==Type.Short[0]:
            return struct.unpack("<"+"%dH"%icount,data[:icount*2])
        elif itype==Type.Long[0]:
            return struct.unpack("<"+"%dI"%icount,data[:icount*4])
        elif itype==Type.Rational[0]:
            rationals = struct.unpack("<"+"%dI"%(icount*2),data[:icount*8])
            return tuple((rationals[i*2],rationals[i*2+1]) for i in range(icount))
        elif itype==Type.Sbyte[0]:
            return struct.unpack("<"+"%db"%icount,data[:icount])
        elif itype==Type.Undefined[0]:
            return data[:icount]
        elif itype==Type.Sshort[0]:
            return struct.unpack("<"+"%dh"%icount,data[:icount*2])
        elif itype==Type.Slong[0]:
            return struct.unpack("<"+"%di"%icount,data[:icount*4])
        elif itype==Type.Srational[0]:
            rationals = struct.unpack("<"+"%di"%(icount*2),data[:icount*8])
            return tuple((rationals[i*2],rationals[i*2+1]) for i in range(icount))
        elif itype==Type.Float[0]:
            return struct.unpack("<"+"%df"%icount,data[:icount*4])
        elif itype==Type.Double[0]:
            return struct.unpack("<"+"%dd"%icount,data[:icount*8])
        elif itype==Type.IFD[0]:
            return struct.unpack("<"+"%dI"%icount,data[:icount*4])

    def readIfdEntry(self,ifd,ifdEntry,data):
        itag,itype,icount,ival = ifdEntry
        tagTypeSize = Types[itype][0][1]
        totalSize = tagTypeSize * icount
        if totalSize > 4:
            data = self.readFrom(ival,totalSize)

        values = self.decodeTagData(itype,icount,data)
           
        IfdName = IfdLookup.get(itag,"Unknown")
        if itag==Tag.NewSubfileType[0]:
            ifd.subFileType = ival
            if ifd.isFull():
                self.FULL_IFD = ifd
            elif ifd.isThumb():
                self.THUMB_IFD = ifd
        elif itag==Tag.ImageWidth[0]:
            ifd.width = ival
            if self.log: print "Width:",ifd.width 
        elif itag==Tag.ImageLength[0]:
            ifd.length = ival
            if self.log: print "Length:",ifd.length 
        elif itag==Tag.SubIFD[0]:
            if self.log: print "Reading SubIFDs"
            for suboffset in values:
                subifd,dummy = self.readIfd(suboffset)
                if dummy!=0:
                    print "Expected nextOffset after subIFD = 0!"
                ifd.subIFDs.append(subifd)
        elif itag==Tag.EXIF_IFD[0]:
            if self.log: print "Reading EXIF IFD"
            ifd.EXIF_IFD,dummy = self.readIfd(ival)
            if dummy!=0:
                print "Expected nextOffset after EXIF_IFD = 0!"
        elif itag==Tag.RowsPerStrip[0]:
            ifd.RowsPerStrip = ival
        elif itag==Tag.PlanarConfiguration[0]:
            ifd.PlanarConfiguration = ival
        
        ifdEntry = (itag,itype,icount,values)
        if self.log: print IfdName,ifdEntry 
        return ifdEntry 

    def write(self,filename):
        pass 

def testDngDirRead(path):
    dngs = [i for i in os.listdir(sys.argv[1]) if i.lower().endswith(".dng")]
    print "Reading DNGs (%d)"%len(dngs)
    count = 0
    last = time.time()
    for n in dngs:
        if count%10==0:
            now = time.time()
            took = now-last
            rate = 10.0/took
            print count,"...",took,rate
            last = now
        fn = os.path.join(sys.argv[1],n)
        d = DNG(parse=False)
        d.readFileIn(fn)
        d.parse()
        if d.THUMB_IFD:
            thumb = d.THUMB_IFD.stripsCombined()
        if d.THUMB_IFD:
            full = d.FULL_IFD.stripsCombined()
        d.close()
        count+=1
    print "Done"

def testReadDng(filename):
    d = DNG(log=True,parse=True)
    d.readFile(filename)
    if d.THUMB_IFD:
        thumb = d.THUMB_IFD.stripsCombined()
        print "Thumb:"
        print len(thumb)
    if d.THUMB_IFD:
        full = d.FULL_IFD.stripsCombined()
        print "Full:"
        print len(full)
    d.close()

if __name__ == '__main__':
    if os.path.isdir(sys.argv[1]):
        testDngDirRead(sys.argv[1])
    else:
        testReadDng(sys.argv[1])

