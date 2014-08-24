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

def loadAllLuts():
    config = os.path.expanduser("~/.mlrawviewer/")
    if not os.path.exists(config):
        os.mkdir(config)
    root = os.path.expanduser("~/.mlrawviewer/lut/")
    if not os.path.exists(root):
        os.mkdir(root)
    lutfiles = os.listdir(root)
    lutfiles.sort()
    luts3d = []
    lut3dfns = []
    luts1d = []
    lut1dfns = []
    for f in lutfiles:
        fn = os.path.join(root,f)
        try:
            lut = loadLut(fn)
        except:
            continue
        if lut.dim()==1:
            lut1dfns.append(fn)
            luts1d.append(lut)
        elif lut.dim()==3:
            lut3dfns.append(fn)
            luts3d.append(lut)
    return luts3d,lut3dfns,luts1d,lut1dfns

if __name__ == '__main__':
    lut = loadLut(sys.argv[1])
    print "Dimensions:",lut.dim()
    print "Length:",lut.len()
    print "Elements:",len(lut.lut())


