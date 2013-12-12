import sys,zlib,struct
import numpy as np
import GLCompute

class Font(object):
    def __init__(self,filename):
        self.load(filename)
        self.fontex = None
    def load(self,filename):
        fontfile = file(filename,'rb')
        signature,clen,glen,alen,klen,vlen = struct.unpack("<IIIIII",fontfile.read(24))
        if signature != 0x0061F047:
            raise Exception("Not a valid GLF font file")

        self.coords = np.fromstring(zlib.decompress(fontfile.read(clen)),dtype=np.float32)
        self.geometry = np.fromstring(zlib.decompress(fontfile.read(glen)),dtype=np.int16)
        self.geometry = self.geometry.reshape((8,self.geometry.shape[0]/8))
        self.kerningkeys = np.fromstring(zlib.decompress(fontfile.read(klen)),dtype=np.uint16)
        self.kerningvals = np.fromstring(zlib.decompress(fontfile.read(vlen)),dtype=np.int16)
        self.atlas= zlib.decompress(fontfile.read(alen))

        self.kerning = {}
        for i,k in enumerate(self.kerningkeys):
            self.kerning[k] = self.kerningvals[i]
        #print len(self.atlas),len(self.kerningkeys)
        #print self.kerning

        fontfile.close()

    def texture(self):
        if self.fontex: 
            return self.fontex
        self.fontex = GLCompute.Texture((1024,1024),rgbadata=self.atlas,hasalpha=False,mono=True,sixteen=False,mipmap=True)
        return self.fontex

if __name__ == '__main__':
    f = Font(sys.argv[1])


