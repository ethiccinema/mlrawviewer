#!/usr/bin/python2.7
"""
Convert a Magic Lantern RAW or MLV file into a "CinemaDNG" sequence
"""
# standard python imports. Should not be missing
import sys,struct,os,math,time,datetime

# So we can use modules from the main dir
root = os.path.split(sys.path[0])[0]
sys.path.append(root)

import numpy as np

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
    at(e,DNG.Tag.StripOffsets,0)
    at(e,DNG.Tag.Orientation,1)
    at(e,DNG.Tag.SamplesPerPixel,1)
    at(e,DNG.Tag.RowsPerStrip,r.height())
    ifd.RowsPerStrip = r.height()
    at(e,DNG.Tag.StripByteCounts,0)
    at(e,DNG.Tag.PlanarConfiguration,1) # Chunky
    atm(e,DNG.Tag.Software,"MlRawViewer")
    atm(e,DNG.Tag.CFARepeatPatternDim,(2,2)) # No compression
    atm(e,DNG.Tag.CFAPattern,(0,1,1,2)) # No compression
    at(e,DNG.Tag.Compression,1) # No compression
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
    for i in range(r.frames()):
        print i
        r.preloadFrame(i)
        f = r.frame(i)
        ifd._strips = [np.frombuffer(f.rawdata,dtype=np.uint16).byteswap().tostring()]
        d.writeFile(sys.argv[2]+"_%05d.dng"%i)

if __name__ == '__main__':
    sys.exit(main())
