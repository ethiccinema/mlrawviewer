# Parse lossless JPEG (1992 version)
import array,struct
class lj92(object):
    def __init__(self):
        pass
    def parse(self,data):
        self.ix = 0
        self.data = array.array('B',data)
        """
        for cn,c in enumerate(self.data):
            if cn%16==0:
                print
                print "%04x\t"%cn,
            print "%02x"%c,
        print
        """
        self.findSoI()
    def find(self):
        #print "ix",self.ix
        ix = self.ix
        while 1:
            while self.data[ix] != 0xFF:
                ix += 1
            ix += 2
            self.ix = ix
            return self.data[self.ix-1]
        return 0
    def findSoI(self):
        if self.find()==0xd8:
            return self.parseImage()
    def parseImage(self):
        print "Parsing image"
        while 1:
            nextMarker = self.find()
            #print "%x"%nextMarker
            if nextMarker == 0xc4:
                self.parseHuff()
            elif nextMarker == 0xc3:
                self.parseSof3()
            elif nextMarker == 0xfe: # Comment
                self.parseBlock(nextMarker)
            elif nextMarker == 0xd9: # End of image
                break
            elif nextMarker == 0xda:
                self.parseScan()
            else:
                self.parseBlock(nextMarker)
        print "Parsing image complete"
    def nextbit(self):
        if self.cnt == 0:
            self.b = self.data[self.ix]
            #print "b:%x "%self.b,
            self.ix = self.ix + 1
            self.cnt = 8
            if self.b == 0xff:
                self.b2 = self.data[self.ix]
                self.ix = self.ix + 1
                #if self.b2 == 0:
                # Should handle DNL here
        bit = self.b >> 7
        self.cnt = self.cnt - 1
        self.b = (self.b << 1)&0xFF
        return bit
    def decode(self):
        i = 1
        code = self.nextbit()
        while code > self.maxcode[i]:
            i = i+1
            code = (code << 1) + self.nextbit()
        j = self.valptr[i]
        j = j + code - self.mincode[i]
        value = self.huffval[j]
        return value
    def receive(self,ssss):
        i = 0
        v = 0
        while i != ssss:
            i = i+1
            v = (v<<1) + self.nextbit()
        return v
    def extend(self,v,t):
        vt = 2 ** (t-1)
        if v < vt:
            vt = (-1 << t) + 1
            v = v + vt
        return v
    def parseScan(self):
        scanhead = struct.unpack('>HB',self.data[self.ix:self.ix+3])
        comp = struct.unpack('>'+'BB'*scanhead[1],self.data[self.ix+3:self.ix+3+2*scanhead[1]])
        sehl = struct.unpack('>BBB',self.data[self.ix+3+2*scanhead[1]:self.ix+scanhead[0]])
        #print "scan",scanhead,comp,sehl
        pred = sehl[0]
        self.ix += scanhead[0]
        self.cnt = 0
        # Now need to decode huffman coded values
        c = 0
        pixels = self.y * self.x
        out = array.array('H','\0\0'*pixels)
        # First pixel predicted from base value
        t = self.decode()
        diff = self.receive(t)
        diff = self.extend(diff,t)
        Px = 1 << (self.bits-1)
        left = Px + diff
        out[0] = left
        #print out[c]
        c = c + 1
        # Rest of first row predicted from left pixel (not great for bayer)
        while c<self.x:
            t = self.decode()
            diff = self.receive(t)
            diff = self.extend(diff,t)
            Px = left
            left = Px + diff
            out[c] = left
            #print out[c]
            c = c + 1
        # Rest predicted based on scan chosen predictor
        # (Usually using hue change of adjacent colour)
        while c<pixels:
            t = self.decode()
            diff = self.receive(t)
            diff = self.extend(diff,t)
            if pred==0:
                # No prediction... should not be used
                pass
            elif pred==1:
                #Px = Ra
                pass
            elif pred==2:
                #Px = Rb
                pass
            elif pred==3:
                #Px = Rc
                pass
            elif pred==4:
                #Px=Ra + Rb - Rc
                pass
            elif pred==5:
                #Px = Ra + ((Rb - Rc)/2) a)
                pass
            elif pred==6:
                Px = out[c-self.x] + ((left - out[c-self.x-1])>>1)
            elif pred==7:
                #Px = (Ra + Rb)/2
                pass
            left = Px + diff
            out[c] = left
            #print c,pixels,out[c]
            c = c + 1
        #for i in range(len(out)):
        #    out[i] = (out[i]>>8)|((out[i]&0xFF)<<8)
        self.image = out
    def parseBlock(self,marker):
        blockhead = struct.unpack('>H',self.data[self.ix:self.ix+2])
        #print "block %x"%marker,blockhead[0]
        self.ix += blockhead[0]
    def parseHuff(self):
        huffhead = struct.unpack('>HB16B',self.data[self.ix:self.ix+19])
        bits = array.array('i',huffhead[-17:])
        bits[0] = 0
        huffval = self.data[self.ix+19:self.ix+huffhead[0]]
        self.ix += huffhead[0]
        # Generate huffman table
        k = 0
        i = 1
        j = 1
        huffsize = array.array('i')
        while i<=16:
            while j<=bits[i]:
                huffsize.append(i)
                k = k+1
                j = j+1
            i = i+1
            j = 1
        huffsize.append(0)
        lastk = k
        huffcode = array.array('i')
        k = 0
        code = 0
        si = huffsize[0]

        while 1:
            while huffsize[k] == si:
                huffcode.append(code)
                code = code+1
                k = k+1
            if huffsize[k] == 0:
                break
            while huffsize[k] != si:
                code = code << 1
                si = si + 1

        ehufco = array.array('i',[0]*lastk)
        ehufsi = array.array('i',[0]*lastk)
        k = 0
        while k < lastk:
            i = huffval[k]
            ehufco[i] = huffcode[k]
            ehufsi[i] = huffsize[k]
            k = k+1

        i = 0
        j = 0

        maxcode = array.array('i',[0]*17)
        mincode = array.array('i',[0]*17)
        valptr = array.array('i',[0]*17)
        while 1:
            while 1:
                i = i+1
                if i>16:
                    break
                if bits[i]!=0:
                    break
                maxcode[i] = -1
            if i>16:
                break
            valptr[i] = j
            mincode[i] = huffcode[j]
            j = j+bits[i]-1
            maxcode[i] = huffcode[j]
            j = j+1
        self.maxcode = maxcode
        self.mincode = mincode
        self.valptr = valptr
        self.huffval = huffval
        #print "huffman table",huffhead,huffval,huffsize,huffcode,ehufco,ehufsi,mincode,maxcode,valptr
    def parseSof3(self):
        #print "Lossless sequential huffman coded"
        header = struct.unpack('>HBHHBBBB',self.data[self.ix:self.ix+11])
        Lf,P,Y,X,Nf,Ci,HV,Tqi = header
        self.y = Y
        self.x = X
        self.bits = P
        #print header,"%x"%HV
        self.ix += Lf
