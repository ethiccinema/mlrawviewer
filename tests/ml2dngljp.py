#!/usr/bin/python2.7
"""
Convert a Magic Lantern RAW or MLV file into a "CinemaDNG" sequence
"""
# standard python imports. Should not be missing
import sys,struct,os,math,time,datetime,array

# So we can use modules from the main dir
root = os.path.split(sys.path[0])[0]
sys.path.append(root)

import numpy as np
import bitunpack

# Now import our own modules
import MlRaw,DNG

def at(entries,tag,val):
    entries.append((tag[0],tag[1][0],1,(val,)))
def atm(entries,tag,val):
    entries.append((tag[0],tag[1][0],len(val),val))

def main():
    filename = sys.argv[1]
    r = MlRaw.loadRAWorMLV(filename)
    d = DNG.DNG()
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
    at(e,DNG.Tag.BitsPerSample,14)
    ifd.BitsPerSample = (14,)
    at(e,DNG.Tag.Compression,1) # No compression
    at(e,DNG.Tag.PhotometricInterpretation,32803) # CFA
    at(e,DNG.Tag.FillOrder,1)
    atm(e,DNG.Tag.Make,"Canon")
    atm(e,DNG.Tag.Model,"EOS")
    ifd.TileWidth = r.width()/2
    at(e,DNG.Tag.TileWidth,r.width()/2)
    at(e,DNG.Tag.TileLength,r.height())
    atm(e,DNG.Tag.TileOffsets,(0,0))
    atm(e,DNG.Tag.TileByteCounts,(0,0))
    at(e,DNG.Tag.Orientation,1)
    at(e,DNG.Tag.SamplesPerPixel,1)
    #at(e,DNG.Tag.RowsPerStrip,r.height())
    #ifd.RowsPerStrip = r.height()
    #at(e,DNG.Tag.StripByteCounts,0)
    at(e,DNG.Tag.PlanarConfiguration,1) # Chunky
    atm(e,DNG.Tag.Software,"MlRawViewer")
    atm(e,DNG.Tag.CFARepeatPatternDim,(2,2)) # No compression
    atm(e,DNG.Tag.CFAPattern,(0,1,1,2)) # No compression
    at(e,DNG.Tag.Compression,7) # No compression
    atm(e,DNG.Tag.DNGVersion,(1,4,0,0))
    atm(e,DNG.Tag.UniqueCameraModel,"Canon EOS")
    at(e,DNG.Tag.BlackLevel,r.black)
    at(e,DNG.Tag.WhiteLevel,r.white)
    atm(e,DNG.Tag.DefaultCropOrigin,(0,0))
    atm(e,DNG.Tag.DefaultCropSize,(r.width(),r.height()))
    m = [(int(v*10000),10000) for v in r.colorMatrix.A1]
    atm(e,DNG.Tag.ColorMatrix1,m)
    atm(e,DNG.Tag.AsShotNeutral,((473635,1000000),(1000000,1000000),(624000,1000000)))
    at(e,DNG.Tag.FrameRate,(25000,1000))
    import zlib,array

    minlevel = 2048
    delin = array.array('H',[0 for i in range(2**14)])
    for i in range(minlevel,2048+minlevel):
        delin[i] = i-minlevel
    for i in range(2048+minlevel,4096+minlevel):
        delin[i] = 2048+((i-minlevel-2048)>>1)
    for i in range(4096+minlevel,8192+minlevel):
        delin[i] = 3072+((i-minlevel-4096)>>3)
    for i in range(8192+minlevel,16384):
        delin[i] = 3584+((i-minlevel-8192)>>4)
    delin = delin.tostring()
    lin = array.array('H',[0 for i in range(2**12)])
    for i in range(2048):
        lin[i] = i+minlevel
    for i in range(2048,3072):
        lin[i] = ((i-2048)<<1)+minlevel+2048
    for i in range(3072,3584):
        lin[i] = ((i-3072)<<3)+minlevel+4096
    for i in range(3584,4096):
        lin[i] = ((i-3584)<<4)+minlevel+8192
    lin = lin.tostring()

    for i in range(1,r.frames()):
        r.preloadFrame(i)
        f = r.frame(i)
        f.convert()
        #compressed = bitunpack.pack16tolj(f.rawimage,f.width*2,f.height/2,14,0,f.width,0,"")
        #tile1l = bitunpack.pack16tolj(f.rawimage,f.width,f.height/2,16,0,f.width/2,f.width/2,delin)
        #tile2l = bitunpack.pack16tolj(f.rawimage,f.width,f.height/2,16,f.width,f.width/2,f.width/2,delin)
        tile2 = bitunpack.pack16tolj(f.rawimage,f.width,f.height/2,16,f.width,f.width/2,f.width/2,"")
        tile1 = bitunpack.pack16tolj(f.rawimage,f.width,f.height/2,16,0,f.width/2,f.width/2,"")
        print len(tile1),len(tile2),len(tile1)+len(tile2)
        #print len(tile1l),len(tile2l),len(tile1l)+len(tile2l)
        #image = array.array('H',"\0\0"*(f.width*f.height))
        #bitunpack.unpackljto16(buffer(compressed),image,0,f.width,0,"")
        #bitunpack.unpackljto16(str(tile1),image,0,f.width/2,f.width/2,"")
        #bitunpack.unpackljto16(str(tile2),image,f.width,f.width/2,f.width/2,"")
        """
        il = 256
        one = f.rawimage.tostring()
        two = image.tostring()
        if one != two:
            print "different!"
        orig = len(f.rawdata)
        comp = len(tile1)+len(tile2)
        compl = len(tile1l)+len(tile2l)
        print orig,comp,compl,float(comp)/float(orig),float(compl)/float(orig)
        """
        """
        fi = file("%d.raw"%i,'wb')
        fi.write(f.rawimage)
        fi.close()
        break
        """
        ifd._tiles = [tile1,tile2]
        d.writeFile(sys.argv[2]+"_%05d.dng"%i)
        #break

if __name__ == '__main__':
    sys.exit(main())
