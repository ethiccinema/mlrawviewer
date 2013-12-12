#!/usr/bin/python2

import sys,struct
from freetype import *
import numpy as np
import zlib

def generateFont(ttfFontFileName, glFontFileName):
    face = Face(ttfFontFileName)
    fontSize = 60
    face.set_char_size(fontSize*64, 0, 16*72, 72)
    pen = Vector(0,0)
    matrix = Matrix( int((1.0/16.0) * 0x10000L), int((0.0) * 0x10000L),
                             int((0.0)    * 0x10000L), int((1.0) * 0x10000L) )
    face.set_transform( matrix, pen )
    flags = FT_LOAD_RENDER | FT_LOAD_FORCE_AUTOHINT
    atlas = np.zeros((1024,1024),dtype=np.uint8) 
    texcoords = np.zeros((4,256),dtype=np.float32)
    geometry = np.zeros((8,256),dtype=np.int16)
    kerning = []
    for i in range(256):
        face.load_char(chr(i), flags)
        g = face.glyph
        b = g.bitmap
        #print len(b.buffer),g.bitmap_left,g.bitmap_top,b.rows,b.width,b.pitch
        #if b.rows>64 or b.width>64:
        #    print i,chr(i),b.rows,b.width,len(b.buffer)
        bitmap = np.array(b.buffer,dtype=np.uint8).reshape(b.rows,b.pitch)
        ix = i%16
        iy = i/16
        x = ix*64
        y = iy*64
        #print i,chr(i),ix,iy,x,y,bitmap.shape
        # Try to position in middle of atlas square
        t = (64-bitmap.shape[0])/2
        l = (64-bitmap.shape[1])/2
        print t,l,bitmap.shape,x,y,y+t,x+l
        atlas[y+t:y+t+bitmap.shape[0],x+l:x+l+bitmap.shape[1]] = bitmap
        aw = 1024.0
        ah = 1024.0
        texcoords[:,i] = [float(x)/aw,float(y)/ah,(x+64.0)/aw,(y+64.0)/ah]
        print i,b.rows,b.width,g.bitmap_left,g.bitmap_top,g.advance.x,g.advance.y
        geometry[:,i] = [t,l,b.rows,b.width,g.bitmap_left,g.bitmap_top,g.advance.x,g.advance.y] 
        for j in range(256):
            k = face.get_kerning(j,i,0)
            if k.x!=0:
                kerning.append((i,j,k.x))

    kerningkeys = np.array([i+j<<8 for i,j,k in kerning],dtype=np.uint16) 
    kerningvals = np.array([k for i,j,k in kerning],dtype=np.int16)
    
    zkerningkeys = zlib.compress(kerningkeys,9)
    zkerningvals = zlib.compress(kerningvals,9)
    zatlas = zlib.compress(atlas,9)
    zcoords = zlib.compress(texcoords,9)
    zgeometry = zlib.compress(geometry,9) 
    outfile = file(glFontFileName,'wb')
    outfile.write(struct.pack("<IIIIII",0x0061F047,len(zcoords),len(zgeometry),len(zatlas),len(zkerningkeys),len(zkerningvals)))
    outfile.write(zcoords)
    outfile.write(zgeometry)
    outfile.write(zkerningkeys)
    outfile.write(zkerningvals)
    outfile.write(zatlas)
    outfile.close()

generateFont(sys.argv[1],sys.argv[2])

