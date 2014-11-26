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

import LJ92

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
    FillOrder = (266,Type.Short)
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
    TileWidth = (322,Type.Short)
    TileLength = (323,Type.Short)
    TileOffsets = (324,Type.Long)
    TileByteCounts = (325,Type.Long)
    SubIFD = (330,Type.Long)
    XMP_Metadata = (700,Type.Undefined)
    CFARepeatPatternDim = (33421,Type.Short)
    CFAPattern = (33422,Type.Byte)
    Copyright = (33432,Type.Ascii)
    ExposureTime = (33434,Type.Rational)
    FNumber = (33437,Type.Rational)
    EXIF_IFD = (34665,Type.Long)
    ExposureProgram = (34850,Type.Short)
    PhotographicSensitivity = (34855,Type.Short)
    SensitivityType = (34864,Type.Short)
    ExifVersion = (36864,Type.Undefined)
    DateTimeOriginal = (36867,Type.Ascii)
    ShutterSpeedValue = (37377,Type.Srational)
    ApertureValue = (37378,Type.Rational)
    ExposureBiasValue = (37380,Type.Srational)
    MaxApertureValue = (37381,Type.Rational)
    SubjectDistance = (37382,Type.Rational)
    MeteringMode = (37383,Type.Short)
    Flash = (37385,Type.Short)
    FocalLength = (37386,Type.Rational)
    TIFF_EP_StandardID = (37398,Type.Byte)
    SubsecTime = (37520,Type.Ascii)
    SubsecTimeOriginal = (37521,Type.Ascii)
    FocalPlaneXResolution = (41486,Type.Rational)
    FocalPlaneYResolution = (41487,Type.Rational)
    FocalPlaneResolutionUnit = (41488,Type.Short)
    FocalLengthIn35mmFilm = (41989,Type.Short)
    EXIFPhotoBodySerialNumber = (42033,Type.Ascii)
    EXIFPhotoLensModel = (42036,Type.Ascii)
    DNGVersion = (50706,Type.Byte)
    DNGBackwardVersion = (50707,Type.Byte)
    UniqueCameraModel = (50708,Type.Ascii)
    CFAPlaneColor = (50710,Type.Byte)
    CFALayout = (50711,Type.Short)
    LinearizationTable = (50712,Type.Short)
    BlackLevelRepeatDim = (50713,Type.Short)
    BlackLevel = (50714,Type.Short)
    WhiteLevel = (50717,Type.Short)
    DefaultScale = (50718,Type.Rational)
    DefaultCropOrigin = (50719,Type.Long)
    DefaultCropSize = (50720,Type.Long)
    ColorMatrix1 = (50721,Type.Srational)
    ColorMatrix2 = (50722,Type.Srational)
    CameraCalibration1 = (50723,Type.Srational)
    CameraCalibration2 = (50724,Type.Srational)
    AnalogBalance = (50727,Type.Rational)
    AsShotNeutral = (50728,Type.Rational)
    BaselineExposure = (50730,Type.Srational)
    BaselineNoise = (50731,Type.Rational)
    BaselineSharpness = (50732,Type.Rational)
    BayerGreenSplit = (50733,Type.Long)
    LinearResponseLimit = (50734,Type.Rational)
    CameraSerialNumber = (50735,Type.Ascii)
    AntiAliasStrength = (50738,Type.Rational)
    ShadowScale = (50739,Type.Rational)
    DNGPrivateData = (50740,Type.Byte)
    MakerNoteSafety = (50741,Type.Short)
    CalibrationIlluminant1 = (50778,Type.Short)
    CalibrationIlluminant2 = (50779,Type.Short)
    BestQualityScale = (50780,Type.Rational)
    RawDataUniqueID = (50781,Type.Byte)
    ActiveArea = (50829,Type.Long)
    CameraCalibrationSignature = (50931,Type.Ascii)
    ProfileCalibrationSignature = (50932,Type.Ascii)
    NoiseReductionApplied = (50935,Type.Rational)
    ProfileName = (50936,Type.Ascii)
    ProfileHueSatMapDims = (50937,Type.Long)
    ProfileHueSatMapData1 = (50938,Type.Float)
    ProfileHueSatMapData2 = (50939,Type.Float)
    ProfileEmbedPolicy = (50941,Type.Long)
    PreviewApplicationName = (50966,Type.Ascii)
    PreviewApplicationVersion = (50967,Type.Ascii)
    PreviewSettingsDigest = (50969,Type.Byte)
    PreviewColorSpace = (50970,Type.Long)
    PreviewDateTime = (50971,Type.Ascii)
    NoiseProfile = (51041,Type.Double)
    TimeCodes = (51043,Type.Byte)
    FrameRate = (51044,Type.Srational)
    OpcodeList1 = (51008,Type.Undefined)
    OpcodeList2 = (51009,Type.Undefined)
    ReelName = (51081,Type.Ascii)
    BaselineExposureOffset = (51109,Type.Srational) # 1.4 Spec says rational but mentions negative values?
    NewRawImageDigest = (51111,Type.Byte)

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
        self.ifds = []

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

    def readAll(self):
        """
        Parse all strips
            """
        total = 0
        if self.FULL_IFD:
            s = self.FULL_IFD.strips()
            for st in s:
                total += len(st)
        if self.THUMB_IFD:
            s = self.THUMB_IFD.strips()
            for st in s:
                total += len(st)
        self.stripTotal = total

    def align(self,val):
        return (val+1)&0xFFFFFFE
    def writeTag(self,tag,buf,off,extraDataOff):
        header,extra = self.encodeTagData(tag,extraDataOff)
        buf[off:off+12] = header
        if extra:
            buf[extraDataOff:extraDataOff+len(extra)] = extra
            return len(extra)
        else:
            return 0
    def writeIfd(self,buf,off,ifd):
        entryMap = [] # Used to patch IFD pointers later
        extraDataOff = self.align(off+2+len(ifd.entries)*12+4) # Each entry consumes 12 bytes. Extra data must be aligned to word
        buf[off:off+2] = struct.pack(self.bo+"H",len(ifd.entries))
        off += 2
        ifd.entries
        for e in sorted(ifd.entries):
            extraInc = self.writeTag(e,buf,off,extraDataOff)
            entryMap.append((e[0],off,extraDataOff))
            extraDataOff += extraInc
            off += 12
        buf[off:off+4] = struct.pack(self.bo+"I",0) # Don't support multiple chained IFDs.
        ifd.entryMap = entryMap
        return extraDataOff

    def writeFile(self,filename):
        """
        Write out a new (Cinema)DNG file with the current IFD settings
        This supports copying/modifying DNGs even with unknown tags
        since we should have everything we need when loading from existing file
        """
        if self.log: print "Writing to",filename
        # Prepare everything in an array
        dl = 1000000
        b = bytearray(self.stripTotal + 1000000) # Size of the data + 1M to be sure
        # Prepare file header
        if self.bo == "<":
            byteOrder = "II"
        else:
            byteOrder = "MM"
        b[0:8] = struct.pack(self.bo+"2sHI",byteOrder,42,8) # Will begin immediately after the header
        off = 8

        # Write first IFD block
        ifd0len = self.writeIfd(b,off,self.ifds[0])
        off += ifd0len
        # Write any subIFD
        subifd = None
        exififd = None
        for tag,offset,extraOffset in self.ifds[0].entryMap:
            if tag == Tag.SubIFD[0]:
                subifd = (offset,extraOffset)
            if tag == Tag.EXIF_IFD[0]:
                exififd = (offset,extraOffset)
        for sindex,sifd in enumerate(self.ifds[0].subIFDs):
            # Fix up link to this subIFD in IFD0
            if len(self.ifds[0].subIFDs)==1:
                b[subifd[0]+8:subifd[0]+12] = struct.pack(self.bo+"I",off)
            else:
                b[subifd[1]+4*sindex:subifd[1]+4*sindex+4] = struct.pack(self.bo+"I",off)
            off += self.writeIfd(b,off,sifd)

        # Write EXIF IFD
        if self.ifds[0].EXIF_IFD:
            # Fix up link to EXIF_IFD in IFD0
            b[exififd[0]+8:exififd[0]+12] = struct.pack(self.bo+"I",off)
            off += self.writeIfd(b,off,self.ifds[0].EXIF_IFD)

        # Write first strips
        if self.ifds[0].hasStrips():
            off += self.ifds[0].writeStrips(b,off)
        elif self.ifds[0].hasTiles():
            off += self.ifds[0].writeTiles(b,off)

        # Write subifd strips
        for sindex,sifd in enumerate(self.ifds[0].subIFDs):
            if sifd.hasStrips():
                off += sifd.writeStrips(b,off)
            elif sifd.hasTiles():
                off += sifd.writeTiles(b,off)

        # Done with preparation

        # Write the whole file to disk
        outfile = file(filename,'wb')
        outfile.write(b[:off])
        outfile.close()

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
        elif byteOrder == 0x4D4D: # Big endian
            if self.log: print "Big endian"
            self.bo = ">"
        valid,firstIfdOffset = struct.unpack(self.bo+"HI",h[2:])
        if valid != 42:
            raise IOError
        return firstIfdOffset

    class IFD(object):
        def __init__(self,dng):
            self.log = dng.log
            self.dng = dng
            self.entries = []
            self.tags = {}
            self.subIFDs = []
            self.subFileType = None
            self.EXIF_IFD = None
            self.width = None
            self.length = None
            self.RowsPerStrip = None
            self.TileWidth = None
            self.PlanarConfiguration = None
            self.BitsPerSample = None
            self._strips = None
            self._tiles = None
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
        def hasStrips(self):
            if self.RowsPerStrip: return True
            else: return False
        def hasTiles(self):
            if self.TileWidth: return True
            else: return False
        def strips(self):
            if not self.hasStrips(): return None
            if self._strips: return self._strips
            # Load the strips
            if not self.RowsPerStrip: return IOError
            if not self.length: raise IOError
            if not self.PlanarConfiguration: raise IOError
            if self.PlanarConfiguration != 1:
                if self.log: print "Unsupported PlanarConfiguration = ",self.PlanarConfiguration
                raise IOError
            StripsPerImage = self.RowsPerStrip * self.length
            StripByteCounts = self.tags[Tag.StripByteCounts[0]][3]
            StripOffsets = self.tags[Tag.StripOffsets[0]][3]
            self._strips = []
            for byteCount,offset in zip(StripByteCounts,StripOffsets):
                strip = self.dng.readFrom(offset,byteCount)
                self._strips.append(strip)
            return self._strips
        def tiles(self):
            if not self.hasTiles(): return None
            if self._tiles: return self._tiles
            TileLength = self.tags[Tag.TileLength[0]][3][0]
            ImageWidth = self.tags[Tag.ImageWidth[0]][3][0]
            ImageLength = self.tags[Tag.ImageLength[0]][3][0]
            TileByteCounts = self.tags[Tag.TileByteCounts[0]][3]
            TileOffsets = self.tags[Tag.TileOffsets[0]][3]
            TilesAcross = (ImageWidth + self.TileWidth - 1) / self.TileWidth
            TilesDown = (ImageLength + TileLength - 1) / TileLength
            TilesPerImage = TilesAcross * TilesDown
            #print TileLength,ImageWidth,ImageLength,TileByteCounts,TileOffsets,self.TileWidth*TilesAcross,TileLength*TilesDown
            self._tiles = []
            for byteCount,offset in zip(TileByteCounts,TileOffsets):
                tile = self.dng.readFrom(offset,byteCount)
                self._tiles.append(tile)
            return self._tiles
        def stripsCombined(self):
            s = self.strips()
            if len(s)==1:
                return s[0]
            else:
                return ''.join(s)
        def writeStrips(self,buf,offset):
            if not self._strips: raise IOError
            if not self.BitsPerSample: raise IOError
            if not self.RowsPerStrip: raise IOError
            for tag,toffset,extraOffset in self.entryMap:
                if tag == Tag.StripByteCounts[0]:
                    sbc = (toffset,extraOffset)
                if tag == Tag.StripOffsets[0]:
                    so = (toffset,extraOffset)
            StripsPerImage = self.RowsPerStrip * self.length
            BytesPerRow = self.width * sum(self.BitsPerSample) / 8
            BytesPerStrip = BytesPerRow * self.RowsPerStrip
            # Break up self._strips according to these settings
            left = len(self._strips)
            stripoff = 0
            stripNum = 0
            for s in self._strips:
                stripLen = len(s)
                buf[offset:offset+stripLen] = s
                if len(self._strips)==1:
                    i = 0
                    o = 8
                else:
                    i = 1
                    o = stripNum*4
                buf[so[i]+o:so[i]+o+4] = struct.pack(self.dng.bo+"I",offset)
                buf[sbc[i]+o:sbc[i]+o+4] = struct.pack(self.dng.bo+"I",stripLen)
                offset += stripLen
                left -= stripLen
                stripoff += stripLen
                stripNum += 1
            return offset
        def writeTiles(self,buf,offset):
            if not self._tiles: raise IOError
            for tag,toffset,extraOffset in self.entryMap:
                if tag == Tag.TileByteCounts[0]:
                    sbc = (toffset,extraOffset)
                if tag == Tag.TileOffsets[0]:
                    so = (toffset,extraOffset)
            tileoff = 0
            tileNum = 0
            for t in self._tiles:
                tileLen = len(t)
                buf[offset:offset+tileLen] = t
                if len(self._tiles)==1:
                    i = 0
                    o = 8
                else:
                    i = 1
                    o = tileNum*4
                buf[so[i]+o:so[i]+o+4] = struct.pack(self.dng.bo+"I",offset)
                buf[sbc[i]+o:sbc[i]+o+4] = struct.pack(self.dng.bo+"I",tileLen)
                offset += tileLen
                tileNum += 1
            return offset

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

    def encodeTagData(self,tag,extraOffset):
        #print tag
        itag,itype,icount,data = tag
        if itype==Type.Invalid[0]:
            raise IOError
        elif itype==Type.Byte[0]:
            values = struct.pack(self.bo+"%dB"%icount,*data[:icount])
        elif itype==Type.Ascii[0]:
            values = struct.pack(self.bo+"%ds"%icount,data[:icount])
        elif itype==Type.Short[0]:
            values = struct.pack(self.bo+"%dH"%icount,*data[:icount])
        elif itype==Type.Long[0]:
            values = struct.pack(self.bo+"%dI"%icount,*data[:icount])
        elif itype==Type.Rational[0]:
            flattened = [e for nd in data[:icount] for e in nd]
            values = struct.pack(self.bo+"%dI"%(icount*2),*flattened)
        elif itype==Type.Sbyte[0]:
            values = struct.pack(self.bo+"%db"%icount,*data[:icount])
        elif itype==Type.Undefined[0]:
            values = data[:icount]
        elif itype==Type.Sshort[0]:
            values = struct.unpack(self.bo+"%dh"%icount,*data[:icount])
        elif itype==Type.Slong[0]:
            values = struct.pack(self.bo+"%di"%icount,*data[:icount])
        elif itype==Type.Srational[0]:
            flattened = [e for nd in data[:icount] for e in nd]
            values = struct.pack(self.bo+"%di"%(icount*2),*flattened)
        elif itype==Type.Float[0]:
            values = struct.pack(self.bo+"%df"%icount,*data[:icount])
        elif itype==Type.Double[0]:
            values = struct.pack(self.bo+"%dd"%icount,*data[:icount])
        elif itype==Type.IFD[0]:
            values = struct.pack(self.bo+"%dI"%icount,*data[:icount])
        if len(values)>4:
            header = struct.pack(self.bo+"HHII",itag,itype,icount,extraOffset)
            extra = values
        else: # Value embedded
            # Pad values to 4 bytes
            values += chr(0)*(4-len(values))
            header = struct.pack(self.bo+"HHI4s",itag,itype,icount,values)
            extra = None
        return header,extra

    def decodeTagData(self,itype,icount,data):
        if itype==Type.Invalid[0]:
            raise IOError
        elif itype==Type.Byte[0]:
            return struct.unpack(self.bo+"%dB"%icount,data[:icount])
        elif itype==Type.Ascii[0]:
            return struct.unpack(self.bo+"%ds"%icount,data[:icount])[0]
        elif itype==Type.Short[0]:
            return struct.unpack(self.bo+"%dH"%icount,data[:icount*2])
        elif itype==Type.Long[0]:
            return struct.unpack(self.bo+"%dI"%icount,data[:icount*4])
        elif itype==Type.Rational[0]:
            rationals = struct.unpack(self.bo+"%dI"%(icount*2),data[:icount*8])
            return tuple((rationals[i*2],rationals[i*2+1]) for i in range(icount))
        elif itype==Type.Sbyte[0]:
            return struct.unpack(self.bo+"%db"%icount,data[:icount])
        elif itype==Type.Undefined[0]:
            return data[:icount]
        elif itype==Type.Sshort[0]:
            return struct.unpack(self.bo+"%dh"%icount,data[:icount*2])
        elif itype==Type.Slong[0]:
            return struct.unpack(self.bo+"%di"%icount,data[:icount*4])
        elif itype==Type.Srational[0]:
            rationals = struct.unpack(self.bo+"%di"%(icount*2),data[:icount*8])
            return tuple((rationals[i*2],rationals[i*2+1]) for i in range(icount))
        elif itype==Type.Float[0]:
            return struct.unpack(self.bo+"%df"%icount,data[:icount*4])
        elif itype==Type.Double[0]:
            return struct.unpack(self.bo+"%dd"%icount,data[:icount*8])
        elif itype==Type.IFD[0]:
            return struct.unpack(self.bo+"%dI"%icount,data[:icount*4])

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
            ifd.PlanarConfiguration = values[0]
        elif itag==Tag.BitsPerSample[0]:
            ifd.BitsPerSample = values
        elif itag==Tag.TileWidth[0]:
            ifd.TileWidth = ival
        elif itag==Tag.TileLength[0]:
            ifd.TileLength = ival

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
        if d.THUMB_IFD.hasStrips():
            thumb = d.THUMB_IFD.stripsCombined()
        elif d.THUMB_IFD.hasTiles():
            thumb = d.THUMB_IFD.tiles()
        print "Thumb:"
        print len(thumb)
    if d.FULL_IFD:
        if d.FULL_IFD.hasStrips():
            full = d.FULL_IFD.stripsCombined()
        elif d.FULL_IFD.hasTiles():
            full = d.FULL_IFD.tiles()
            # Should check here if it's really lossless JPEG....
            lj = LJ92.lj92()
            for fi,t in enumerate(full):
                print fi,len(t)
                lj.parse(t)

                # For debugging/PoC just dump as raw PGM
                im = lj.image
                for i in range(len(im)):
                    im[i] = (im[i]>>8)|((im[i]&0xFF)<<8)
                dump = file("dump%d.pgm"%fi,'wb')
                dump.write("P5 %d %d 16000\n"%(lj.x,lj.y))
                dump.write(im)
                dump.close()

        print "Full:"
        print len(full)
    d.close()

def testCopyDng(dngin,dngout):
    d = DNG(log=True,parse=True)
    d.readFileIn(dngin)
    d.readAll()
    d.writeFile(dngout)
    d.close()

if __name__ == '__main__':
    if os.path.isdir(sys.argv[1]):
        testDngDirRead(sys.argv[1])
    elif len(sys.argv)==2:
        testReadDng(sys.argv[1])
    elif len(sys.argv)==3:
        testCopyDng(sys.argv[1],sys.argv[2])

