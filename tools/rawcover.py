#!/usr/bin/python2.7
"""
rawcover.py
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

This script tries to identify bayer frames from an ML RAW file
in a given file or directory full of files.

It guesses:
- Frame size
- Start point in the file
- Number of frames

It will create a copy of the data with a valid ML RAW footer applied

Good luck!

"""

import sys,os,array,threading,Queue,struct


BLOCK_SIZE = 1024*1024*16

def bayer(buf,index,res,resindex,times=1,skip=1):
    i = index
    ri = resindex
    while times>0:
        s0 = buf[i] | buf[i+1]<<8
        s1 = buf[i+2] | buf[i+3]<<8
        s2 = buf[i+4] | buf[i+5]<<8
        s3 = buf[i+6] | buf[i+7]<<8
        s4 = buf[i+8] | buf[i+9]<<8
        s5 = buf[i+10] | buf[i+11]<<8
        s6 = buf[i+12] | buf[i+13]<<8

        res[ri] = s0>>2
        res[ri+1] = s1>>4 | (s0&0x3)<<12            
        res[ri+2] = s2>>6 | (s1&0xF)<<10
        res[ri+3] = s3>>8 | (s2&0x3F)<<8
        res[ri+4] = s4>>10 | (s3&0xFF)<<6
        res[ri+5] = s5>>12 | (s4&0x3FF)<<4
        res[ri+6] = s6>>14 | (s5&0xFFF)<<2
        res[ri+7] = s6&0x3FFF
        i += 14*skip
        ri += 8*skip
        times -= 1

def maybe_bayer(buf,index):
    # 7 bytes of 14bit bayer = 4 samples.
    # Could be RGRG, or GRGR, or GBGB or BGBG
    # Range 2000<->15000
    # Scan 16*14 bytes starting from index to find possible match
    minstats = [0 for i in range(14)]
    avstats = [0.0 for i in range(14)]
    b = array.array('H',(0 for i in xrange(8)))
    for slide in range(16):
        for o in range(14):
            fail = False
            i = index + slide*14 + o
            bayer(buf,i,b,0)
            for j in xrange(8):    
                if b[j]<1000: fail = True

            rdiffav = (abs(b[2]-b[0]) + abs(b[4]-b[2]) + abs(b[6]-b[4]))/3.0
            gdiffav = (abs(b[3]-b[1]) + abs(b[5]-b[3]) + abs(b[7]-b[5]))/3.0

            if fail:
                minstats[o] = minstats[o] + 1
            avstats[o] = avstats[o] + rdiffav + gdiffav
            #print b1,b2,b3,b4,b5,b6,b7,b8,rdiffav,gdiffav,fail
    
    # Check is there likely bayer data and the offset from index
    posbayer = [off for off,mins in enumerate(minstats) if mins==0]
    posbayermin = [(avstats[off],off) for off in posbayer]
    posbayermin.sort()
    if len(posbayermin)==0: return None
    else: 
        #print posbayermin[0]
        return posbayermin[0][1]

def find_width(buf,pixels):
    b = array.array('H',(0 for i in xrange(pixels)))
    bayer(buf,0,b,0,pixels/8)
    #print b[0],b[1],b[2],b[3],b[1280],b[1280+1],b[1280+2],b[1280+3]
    width = 640
    resrg = []
    resgb = []
    while width < 2568:
        rg = 0.0
        gb = 0.0
        for i in range(0,pixels-width-1,2*7):
            rg += abs(b[i] - b[i+width+1])
        for i in range(1,pixels-width,2*7):
            gb += abs(b[i] - b[i+width-1])
        resrg.append((rg,width))
        resgb.append((gb,width))
        width += 8
    resrg.sort()
    resgb.sort()
    #print resrg[:4],resgb[:4]
    if resrg[0][1]==resgb[0][1]:
        return resrg[0][1]
    elif resrg[0][0]<resgb[0][0]:
        return resrg[0][1]
    else:
        return resgb[0][1]
        
    #print b

class reader(threading.Thread):
    def __init__(self,fn,start=0,rlen=None):
        self.f = file(fn,'rb')
        self.f.seek(start)
        self.q = Queue.Queue(4)
        self.l = rlen
        threading.Thread.__init__(self)
        self.daemon = True
        self.start()
    def run(self):
        got = 0
        while 1:
            b = self.f.read(16*1024*1024)
            lb = len(b)
            got += lb
            if self.l:
                if got>self.l:
                    b = b[:-(got-self.l)]
                    self.q.put(b)
                    break
            if lb==0:
                break
            self.q.put(b)
        self.q.put(None)
  
def rescue_rawm(f,startoffset,rawmoffset):
    try:
        f.seek(rawmoffset)
        rawm = f.read(192)
        footer = struct.unpack("4shh46i",rawm)
        print footer 
        expecteddata = footer[3]*footer[4]
        unknownlen = rawmoffset - startoffset
        # Return format: start to copy,zero bytes to prepend,frames
        fullframes = unknownlen/footer[3]
        partframe = unknownlen % footer[3]
        if fullframes == footer[4]:
            return partframe,0,footer[4],0,rawm
        elif fullframes > footer[4]:
            return partframe+(fullframes-footer[4])*footer[3],0,footer[4],0,rawm
        else: # fullframes < footer[4]
            # Missing some frames
            zeroprepend = 0
            if partframe>0:
                zeroprepend = footer[3] - partframe
            if zeroprepend>0:
                fullframes += 1
            footer = list(footer)
            footer[4] = fullframes
            newrawm = struct.pack("4shh46i",*footer)
            return 0,zeroprepend,fullframes,footer[4]-fullframes,newrawm
    except:
        import traceback
        traceback.print_exc()
    return -1,0,0,0,"" # Still "unknown"

def rawmheader(width,height,framesize,frames):
    footer = ('RAWM', width, height, framesize, frames, 1, 23976, 0, -8295664, 1, 71182500, 1268, 2040, 3570, 4526760, 14, 1791, 15000, 0, 0, 1880, 1250, 18, 160, 1268, 2040, 0, 0, 33620224, 1, 4716, 10000, 603, 10000, -830, 10000, -7798, 10000, 15474, 10000, 2480, 10000, -1496, 10000, 1937, 10000, 6651, 10000, 1110)
    rawm = struct.pack("4shh46i",*footer)
    return rawm

def copy(fn,start,clen,ofn,prepend,postpend):
    cr = reader(fn,start,clen)
    rf = file(ofn,'wb')
    if len(prepend)>0:
        rf.write(prepend)
    while 1:
        b = cr.q.get()
        if b == None:
            break
        rf.write(b)
    if len(postpend)>0:
        rf.write(postpend)
    rf.close()

def rescue_norawm(f,start,end,fn,tfn):
    # First, skip any zero bytes at the start
    # e.g. from empty disk sectors
    f.seek(start)
    block = f.read(1024*16)
    while 1:
        lastzero = block.rfind("\0")
        count = block.count("\0",0,lastzero)
        if lastzero == len(block)-1:
            start += len(block)
            block = f.read(1024*16)
        else:
            if lastzero==count:
                start += count+1
                break
            else:
                count2 = block.count("\0",0,count)
                if count2==lastzero:
                    start += lastzero+1
                    break
                else:
                    count = 0
                    for c in block:
                        if c != "\0":
                            break
                        count += 1
                    start += count
                    break
    print "start",start 
    f.seek(start)

    # Is there bayer data immediately after that?
    block = f.read(17*14)
    a = array.array('B',block)
    res = maybe_bayer(a,0)
    if res == 0: # Yes, and aligned
        print "Possible RAW Bayer data found"
        f.seek(start)
        biggerblock = f.read((14*10000)/8)
        a = array.array('B',biggerblock)
        width = find_width(a,10000)
        print "Estimated frame width:",width

        # Try to read whole potential frame
        toread = 14*width*1200/8
        f.seek(start)
        wholeframeplus = f.read(toread)
        a = array.array('B',wholeframeplus)
        pixels = array.array('H',(0 for i in xrange(width*1200)))
        bayer(a,0,pixels,0,1200,width/8)
        frametot = 0.0
        avcount = 0.0
        for h in range(400,1198,2):
            av = 0.0
            for i in range(8):
                av += abs(pixels[h*width+i] - pixels[(h+2)*width+i])
            if avcount>0.0:
                if av > 8.0*(frametot/avcount):
                    break
            frametot += float(av)
            avcount += 1.0
        height = h+2
        print "Estimated frame height:",height
        framesize = 14*width*height/8
        diskframesize = (framesize+0x1000)&0xFFFFF000
        # how many frames in this section?
        sectionlen = end - start
        frames = sectionlen/diskframesize
        partframe = sectionlen%diskframesize
        appendzero = diskframesize - partframe
        f.seek(start+diskframesize)
        block = f.read(17*14)
        a = array.array('B',block)
        res = maybe_bayer(a,0)
        print res
        postpend = ""
        if appendzero>0:
            postpend = "\0"*appendzero
            frames += 1
        print "Copying possibly rescued RAW file with %d frames to"%frames,tfn
        copy(fn,start,end,tfn,"",postpend+rawmheader(width,height,diskframesize,frames))

    return    
    
    # Try to find any likely bayer data
    results = []
    lastres = None
    for check in range(start,end,14*1024*32):
        f.seek(check)
        block = f.read(17*14)
        a = array.array('B',block)
        res = maybe_bayer(a,0)
        print check,res,
        results.append((check,res))
    """
        if res!=None and res==lastres:
            c,r = results[-2]
            f.seek(c+r)
            biggerblock = f.read((14*10000)/8)
            a = array.array('B',biggerblock)
            find_width(a,10000)
        lastres = res
    """
    print results

def recover_file(fn,target):

    rescnum = 0
    targroot = os.path.join(target,os.path.split(fn)[1].replace(".","_"))

    print "Attempting to recover:",fn
    f = file(fn,'rb')
    f.seek(0,os.SEEK_END)
    flen = f.tell()
    f.seek(0)    
    print "File length:",flen

    # First scan entire file for "RAWM" blocks
    print "Scanning file for Magic Lantern RAW headers."
    r = reader(fn)
    v = r.q.get()
    lastv = None
    o = 0
    rawm = []
    while v != None:
        print "%d%%.."%(100.0*float(o)/float(flen)),
        sys.stdout.flush()
        if lastv:
            rawpos = (lastv[-4:]+v[:4]).find("RAWM")
            if rawpos != -1:
                rawm.append(o-4+rawpos)
                #print "RAWM (o)",rawpos+o
        p = 0
        while 1:
            rawpos = v.find("RAWM",p)        
            if rawpos == -1:
                break
            rawm.append(o+rawpos)
            #print "RAWM",rawpos+o
            p = rawpos+1
        lastv = v
        o += len(v)
        v = r.q.get()

    print

    unknown = []

    if len(rawm)>0:
        print "Found %d Magic Lantern RAW headers (that is good!)"%len(rawm)
        start = 0
        for rawm_offset in rawm:
            print rawm_offset
            rstart,rprepend,frames,missing,rawmheader = rescue_rawm(f,start,rawm_offset)
            end = rawm_offset
            if rstart!=-1:
                if rstart>0:
                    unknown.append((start,start+rstart))
                rn = targroot+"_%03d.RAW"%rescnum
                if rprepend==0 and missing==0:
                    print "Copying fully rescued RAW file containing %d frames to"%frames,rn
                else:
                    print "Copying partially rescued RAW file containing %d frames to"%(frames),rn
                    if missing>0:
                        print "- Missing frames = ",missing
                    if rprepend>0:
                        print "- Broken frames = 1"
                prepend = ""
                if rprepend>0:
                    prepend += "\0"*rprepend
                copy(fn,start+rstart,end,rn,prepend,rawmheader)
                rescnum += 1
            else:
                print "Problem rescuing RAW file."
                unknown.append((start,end)) 
            end += len(rawmheader)
            start = end
        if start != flen:
            unknown.append((start,flen))    
    else:
        print "No Magic Lantern RAW headers found."
        unknown.append((0,flen))

    for us,ue in unknown:
        print "Unknown section from",us,"to",ue
        rn = targroot+"_%03d.RAW"%rescnum
        rescue_norawm(f,us,ue,fn,rn)
        rescnum += 1

def recover_dir(dirname,target):
    files = os.listdir(dirname)
    for fn in files:
        recover_file(os.path.join(dirname,fn),target)

def main():
    if len(sys.argv)<1:
        print "Usage: ",sys.argv[0],"source_file_or_dir [target_dir]"
        return
    source = sys.argv[1]
    isdir = os.path.isdir(source)
    if len(sys.argv)>2:
        target = sys.argv[2]
    else:
        if isdir:
            target = source
        else:
            target = os.path.split(source)[0]
    print "Source:",source,
    if isdir: print "(dir)",
    print "Target:",target

    if isdir:
        recover_dir(source,target)
    else:
        recover_file(source,target)

if __name__ == '__main__':
    sys.exit(main())

