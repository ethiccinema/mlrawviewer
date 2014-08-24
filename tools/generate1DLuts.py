#/usr/bin/python2
import sys,os,math

# So we can use modules from the main dir
root = os.path.split(sys.path[0])[0]
sys.path.append(root)

import LUT

"""
Generate log curve LUTs for different numbers of stops DR
0 always maps to 0
1 always maps to 1
16 stops maps input to range 1-65536. log2 maps this to 0-16.0
14 stops maps input to range 1-16384. log2 maps this to 0-14.0
12 stops maps input to range 1-4096. log2 maps this to 0-12.0
10 stops maps input to range 1-1024. log2 maps this to 0-10.0
etc.
"""
def LogLut(n,stops):
    l = LUT.LutCube()
    l.d = 1
    l.n = n
    l.t = "Linear to Log %d"%stops
    premul = math.pow(2.0,stops)-1.0
    scale = premul*1.0/float(l.n-1.0)
    for i in range(l.n):
        f = 1.0+float(i)*scale
        v = math.log(f,2.0)/float(stops)
        l.a.extend((v,v,v))
    return l

"""
Generate sRGB gamma curve
0-0.0031308    y = 12.92*x
0.0031308-1.0  y = (1.0+0.055)*x^(1.0/2.4)-0.055
"""
def sRGBLut(n):
    l = LUT.LutCube()
    l.d = 1
    l.n = n
    l.t = "Linear to sRGB Gamma"
    scale = 1.0/float(l.n-1.0)
    power = 1.0/2.4
    for i in range(l.n):
        f = float(i)*scale
        if f<=0.0031308:
            v = 12.92 * f
        else:
            v = (1.0+0.055)*math.pow(f,power)-0.055
        l.a.extend((v,v,v))
    return l

"""
Generate Rec.709 gamma curve
0-0.018    y = 4.5*x
0.018-1.0  y = 1.099*x^(0.45)-0.099
"""
def Rec709Lut(n):
    l = LUT.LutCube()
    l.d = 1
    l.n = n
    l.t = "Linear to Rec.709 Gamma"
    scale = 1.0/float(l.n-1.0)
    for i in range(l.n):
        f = float(i)*scale
        if f<0.018:
            v = 4.5 * f
        else:
            v = (1.099)*math.pow(f,0.45)-0.099
        l.a.extend((v,v,v))
    return l

"""
Generate Rheinhard global tone map y = x/(1+x) curve
"""
def ReinhardHDRLut(n):
    l = LUT.LutCube()
    l.d = 1
    l.n = n
    l.t = "Linear to HDR Reinhard global tone map"
    scale = 6.0 * 1.0/float(l.n-1.0)
    maxval = 6.0/7.0
    for i in range(l.n):
        f = float(i)*scale
        v = f/((1.0+f)*maxval)
        #print i,f,v
        l.a.extend((v,v,v))
    return l


if not os.path.exists("../LUTS/1D"):
    os.makedirs("../LUTS/1D")
LogLut(2**12,16).save("../LUTS/1D/Log16.cube")
LogLut(2**12,14).save("../LUTS/1D/Log14.cube")
LogLut(2**12,12).save("../LUTS/1D/Log12.cube")
LogLut(2**12,10).save("../LUTS/1D/Log10.cube")
LogLut(2**12,9).save("../LUTS/1D/Log9.cube")
LogLut(2**12,8).save("../LUTS/1D/Log8.cube")
LogLut(2**12,7).save("../LUTS/1D/Log7.cube")
LogLut(2**12,6).save("../LUTS/1D/Log6.cube")
LogLut(2**12,5).save("../LUTS/1D/Log5.cube")
sRGBLut(2**12).save("../LUTS/1D/sRGB.cube")
Rec709Lut(2**12).save("../LUTS/1D/Rec709.cube")
ReinhardHDRLut(2**12).save("../LUTS/1D/HDR.cube")
