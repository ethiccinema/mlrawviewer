"""
LUT.py
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

Utilities and support code for reading,writing and generating different 1D/3D LUT formats
"""

import sys,array,os,math

from Config import config

class LutBase(object):
    def __init__(self,**kwds):
        super(LutBase,self).__init__(**kwds)
        self.d = 0
        self.n = 0
        self.a = array.array('f')
        self.t = ""
    def dim(self):
        return self.d
    def len(self):
        return self.n
    def lut(self):
        return self.a
    def name(self):
        if not hasattr(self,"t"): self.t = ""
        return self.t

class LutCube(LutBase):
    """
    Read 3D LUT files in the .cube format
    Comments follow lines starting with #
    TITLE "string" specifies a title for the LUT to display
    LUT_3D_SIZE n specifies number of samples in 3D
    LUT_1D_SIZE n specifies number of samples in 1D

    """
    def __init__(self,**kwds):
        super(LutCube,self).__init__(**kwds)
    def load(self,filename):
        f = open(filename,'r')
        data = f.read()
        f.close()
        lines = data.split('\n')
        name = os.path.split(filename)[1]
        try:
            name = os.path.splitext(name)[0]
        except:
            pass
        for l in lines:
            l = l.strip()
            if l.startswith("#"):
                continue
            elif l.startswith("TITLE"):
                title = l.split("\"")[1]
                if title.startswith("Generate"):
                    # Useless Resolve comment
                    pass
                else:
                    name = title
                continue
            elif l.startswith("LUT_3D_SIZE"):
                self.d = 3
                self.n = int(l.split()[1])
            elif l.startswith("LUT_1D_SIZE"):
                self.d = 1
                self.n = int(l.split()[1])
            elif len(l.strip())==0:
                continue
            else:
                r,g,b = l.split()
                rgb = (float(r),float(g),float(b))
                self.a.extend(rgb)
        self.t = name
    def save(self,filename):
        l = list()
        l.append("TITLE \"%s\"\n\n"%self.name())
        l.append("# Created by MlRawViewer (https://bitbucket.org/baldand/mlrawviewer)\n\n")
        if self.dim()==1:
            l.append("LUT_1D_SIZE %d\n\n"%self.len())
        elif self.dim==3:
            l.append("LUT_3D_SIZE %d\n\n"%self.len())
        vi = iter(self.a)
        try:
            while 1:
                r = vi.next()
                g = vi.next()
                b = vi.next()
                l.append("%.8f %.8f %.8f\n"%(r,g,b))
        except:
            pass
        final = ''.join(l)
        lutfile = open(filename,'wb')
        lutfile.write(final)
        lutfile.close()

def loadLut(filename):
    if filename.lower().endswith(".cube"):
        lut = LutCube()
        lut.load(filename)
        return lut
    else:
        return None

IDENTITY_3D_LUT = array.array('f',[
            0.0,0.0,0.0,
            1.0,0.0,0.0,
            0.0,1.0,0.0,
            1.0,1.0,0.0,
            0.0,0.0,1.0,
            1.0,0.0,1.0,
            0.0,1.0,1.0,
            1.0,1.0,1.0]).tostring()

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
    l = LutCube()
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
    l = LutCube()
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
    l = LutCube()
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
Generate Reinhard global tone map y = x/(1+x) curve
"""
def ReinhardHDRLut(n):
    l = LutCube()
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

"""
Generate Linear-to-S-Log LUT
"""
def SlogLut(n):
    l = LutCube()
    l.d = 1
    l.n = n
    l.t = "Linear to S-Log"
    scale = (2**14.0)/float(l.n-1.0)
    for i in range(l.n):
        f = float(i)*scale
        v = (379.0*math.log(f/5088.0 + 0.037584, 10.0) + 630.0)/1024.0
        #print i,f,v
        l.a.extend((v,v,v))
    return l

"""
Generate Linear-to-S-Log2 LUT
"""
def Slog2Lut(n):
    l = LutCube()
    l.d = 1
    l.n = n
    l.t = "Linear to S-Log2"
    scale = (2**14.0)/float(l.n-1.0)
    for i in range(l.n):
        f = float(i)*scale
        v = (114.0*math.log(f/270.0 + 1.0, 2.0) + 90.0)/1024.0
        #print i,f,v
        l.a.extend((v,v,v))
    return l


"""
Generate Linear-to-LogC LUT
"""
def LogCLut(n):
    l = LutCube()
    l.d = 1
    l.n = n
    l.t = "Linear to Log-C"
    scale = (2**14.0)/float(l.n-1.0)
    for i in range(l.n):
        f = float(i)*scale
        if f>(88.0/16384.0):
            v = (272.0*math.log(f/950.0, 10.0) + 391.0)/1024.0
        else:
            v = 20480.0*f/1024.0
        #print i,f,v
        l.a.extend((v,v,v))
    return l

"""
Generate Linear-to-C-Log LUT
"""
def ClogLut(n):
    l = LutCube()
    l.d = 1
    l.n = n
    l.t = "Linear to C-Log"
    scale = (2**14.0)/float(l.n-1.0)
    for i in range(l.n):
        f = float(i)*scale
        v = (135.0*math.log(f/320.0 + 1.0, 2.0) + 72.0)/1024.0
        #print i,f,v
        l.a.extend((v,v,v))
    return l

"""
LUT default configuration
"""

LUT3D = config.getState("lut3d")
LUT1D = config.getState("lut1d")

LUT_STANDARD = 1 # Not deletable
LUT_USER = 2 # Deletable

if LUT3D == None:
    LUT3D = list()
if LUT1D == None:
    LUT1D = list()

def generateDefaultLuts():
    global LUT1D
    userluts = [(lut,luttype) for lut,luttype in LUT1D if luttype==LUT_USER]
    standardluts = [(lut,luttype) for lut,luttype in LUT1D if luttype==LUT_STANDARD]
    if len(standardluts)!=19:
        print "Updating standard 1D LUTs"
        for n in [1,2,3,4,5,6,7,8,9,10,11,12]:
            l = LogLut(2**12,n)
            LUT1D.append((l,LUT_STANDARD))
        LUT1D.append((sRGBLut(2**12),LUT_STANDARD))
        LUT1D.append((Rec709Lut(2**12),LUT_STANDARD))
        LUT1D.append((ReinhardHDRLut(2**12),LUT_STANDARD))
        LUT1D.append((SlogLut(2**12),LUT_STANDARD))
        LUT1D.append((Slog2Lut(2**12),LUT_STANDARD))
        LUT1D.append((LogCLut(2**12),LUT_STANDARD))
        LUT1D.append((ClogLut(2**12),LUT_STANDARD))
        LUT1D.extend(userluts)
        config.setState("lut1d",LUT1D)

generateDefaultLuts()

if __name__ == '__main__':
    lut = loadLut(sys.argv[1])
    print "Dimensions:",lut.dim()
    print "Length:",lut.len()
    print "Elements:",len(lut.lut())


