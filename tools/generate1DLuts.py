#/usr/bin/python2
import sys,os,math

# So we can use modules from the main dir
root = os.path.split(sys.path[0])[0]
sys.path.append(root)

import LUT

if not os.path.exists("../LUTS/1D"):
    os.makedirs("../LUTS/1D")
LUT.LogLut(2**12,16).save("../LUTS/1D/Log16.cube")
LUT.LogLut(2**12,14).save("../LUTS/1D/Log14.cube")
LUT.LogLut(2**12,12).save("../LUTS/1D/Log12.cube")
LUT.LogLut(2**12,10).save("../LUTS/1D/Log10.cube")
LUT.LogLut(2**12,9).save("../LUTS/1D/Log9.cube")
LUT.LogLut(2**12,8).save("../LUTS/1D/Log8.cube")
LUT.LogLut(2**12,7).save("../LUTS/1D/Log7.cube")
LUT.LogLut(2**12,6).save("../LUTS/1D/Log6.cube")
LUT.LogLut(2**12,5).save("../LUTS/1D/Log5.cube")
LUT.sRGBLut(2**12).save("../LUTS/1D/sRGB.cube")
LUT.Rec709Lut(2**12).save("../LUTS/1D/Rec709.cube")
LUT.ReinhardHDRLut(2**12).save("../LUTS/1D/HDR.cube")
