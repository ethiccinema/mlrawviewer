/*
bayz.c
Copyright (c) Andrew Baldwin 2014

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

Bayz is a algorithm for compressing raw 14bit bayer
data such as that produced by Canon DSLR cameras.

It works as a preprocessor stage which tries to exploit
similarities in hue and luminance across each row of pixels
before feeding the result to a Finite State Entropy encoder.

It produces similar results or even slightly ahead of 
LZMA applied to the same 14bit data expanded to 16bit.

But it is much, much faster at compression than LZMA.

*/


#include "stdlib.h"
#include "stdio.h"
#include "bayz.h"
#include "fse.h"

typedef unsigned short u16;
typedef unsigned char u8;

static u16* raw14to16(int width, int height, u16* bay14, u16* bay16) 
{
    u16* i = bay14;
    u16* o = bay16;
    int blocks = (width*height)/8;
    while (blocks--) {
       *o++ = (i[0]>>2)&0x3FFF;
       *o++ = ((i[0]&0x3)<<12)|((i[1]>>4)&0xFFF); 
       *o++ = ((i[1]&0xF)<<10)|((i[2]>>6)&0x3FF); 
       *o++ = ((i[2]&0x3F)<<8)|((i[3]>>8)&0xFF); 
       *o++ = ((i[3]&0xFF)<<6)|((i[4]>>10)&0x3F); 
       *o++ = ((i[4]&0x3FF)<<4)|((i[5]>>12)&0xF); 
       *o++ = ((i[5]&0xFFF)<<2)|((i[6]>>14)&0x3); 
       *o++ = (i[6]&0x3FFF); 
       i += 7;
    } 
    return bay16;
}

u16 encode(int val)
{
    u16 encoded = 0;

    if(0)
    {
        return (val>=0)?val:(0x8000|(-val));
    }

    if(0)
    {
        /* positive values dont get encoded, lowest bit is zero */
        if(val < 0)
        {
            /* negative values get 0x80 set, offset to squeeze one bit more into (we dont need two representations of zero) */
            val = -val - 1;
            encoded |= 0x0080;
        }

        encoded |= (val & 0xFF80) << 1;
        encoded |= (val & 0x007F);
    }

    if(1)
    {
        /* positive values dont get encoded, lowest bit is zero */
        if(val < 0)
        {
            /* negative values get lowest bit set, offset to squeeze one bit more into (we dont need two representations of zero) */
            val = -val - 1;
            encoded |= 0x0001;
        }

        encoded |= val << 1;
    }

    return encoded;
}

int decode(u16 val)
{
    int decoded ;
    
    if (0)
    {
        return (val&0x8000)?(-(val&0x7FFF)):val;
    }

    if (0) 
    {   
        if (val&0x0080)
        {
            decoded = -1-(((val & 0xFF00)>>1)|(val & 0x007F));
        } 
        else 
        {
            decoded = ((val & 0xFF00) >> 1)|(val & 0x7F);
        }
    }

    if (1)
    {
        if (val&0x1)
        {
            decoded = -1-((val & 0xFFFE)>>1);
        } 
        else 
        {
            decoded = (val & 0xFFFE) >> 1;
        }
    }

    return decoded;
}


void split_bytes(u16 value, u8 *high, u8 *low)
{
    *high = value >> 8;
    *low = value & 0xFF;
}

static void convertToDiff(int width, int height, u16* raw16, u8* high, u8* low)
{
    u16* r = raw16;  
    int y,x;
    for (y=0;y<height;) {
        int re = r[0];
        int gr = r[1];
        int dr = re;
        int dg = gr;
        split_bytes(encode(dr), &high[0], &low[0]);
        split_bytes(gr, &high[1], &low[1]);
        r += 2; high += 2; low += 2;
        for (x=2;x<width;x+=2) {
            re = r[0];
            gr = r[1];
            dr -= re; 
            dg -= gr; 
            split_bytes(encode(dr), &high[0], &low[0]);
            split_bytes(encode(dg), &high[1], &low[1]);
            dr = (re);
            dg = gr;
            r += 2; high += 2; low += 2;
        }
        y++;
        gr = r[0];
        int bl = r[1];
        int db = bl;
        dg = gr;
        split_bytes(gr, &high[0], &low[0]);
        split_bytes(encode(db), &high[1], &low[1]);
        r += 2; high += 2; low += 2;
        for (x=2;x<width;x+=2) {
            gr = r[0];
            bl = r[1];
            db -= bl; 
            dg -= gr; 
            split_bytes(encode(dg), &high[0], &low[0]);
            split_bytes(encode(db), &high[1], &low[1]);
            db = bl;
            dg = gr;
            r += 2; high += 2; low += 2;
        }
        y++;
    }
}

static void convertFromDiff(int width, int height, u16* raw16, u8* high, u8* low)
{
/*
Invert convertToDiff
*/
    u16* r = raw16;  
    int y,x;
    for (y=0;y<height;) {
        int hl = (high[0]<<8)|low[0];
        int dr = decode(hl);
        hl = (high[1]<<8)|low[1];
        int gr = hl;
        int re = dr;
        r[0] = re;
        r[1] = gr;
        r += 2; high += 2; low += 2;
        for (x=2;x<width;x+=2) {
            hl = (high[0]<<8)|low[0];
            dr = decode(hl);
            hl = (high[1]<<8)|low[1];
            int dg = decode(hl);
            gr = r[-1] - dg;    
            re = r[-2] - dr;
            r[0] = re;
            r[1] = gr;
            r += 2; high += 2; low += 2;
        }
        y++;
        hl = (high[0]<<8)|low[0];
        gr = hl;
        hl = (high[1]<<8)|low[1];
        int db = decode(hl);
        int bl = db;
        r[0] = gr;
        r[1] = bl;
        r += 2; high += 2; low += 2;
        for (x=2;x<width;x+=2) {
            hl = (high[0]<<8)|low[0];
            int dg = decode(hl);
            hl = (high[1]<<8)|low[1];
            db = decode(hl);
            gr = r[-2] - dg;    
            bl = r[-1] - db;
            r[0] = gr;
            r[1] = bl;
            r += 2; high += 2; low += 2;
        }
        y++;
    }
}

unsigned short* bayz_convert14to16(int width, int height, unsigned short* bay14)
{
    u16* bay16 = (u16*)malloc(width*height*sizeof(u16)); 
    if (bay16 != NULL) {
        raw14to16(width,height,bay14,bay16);
    }
    return bay16;
}

int bayz_encode14(int width, int height, unsigned short* bay14, void** bayz)
{
    u16* bay16 = (u16*)malloc(width*height*sizeof(u16)); 
    raw14to16(width,height,bay14,bay16);
    int ret = bayz_encode16(width,height,bay16,bayz);
    free(bay16);
    return ret;
}

int bayz_encode16(int width, int height, unsigned short* bay16, void** bayz)
{
    //printf("bayz_encode: width=%d, height=%d\n",width,height);
    const int headersize = 5*sizeof(int);
    u8* high = (u8*)malloc(width*height*2);
    int fsesize = FSE_compressBound(width*height*2)+headersize;
    void* out = (void*)malloc(fsesize);
    if ((high==NULL)||(out==NULL)) {
        free(high);
        free(out);
        return BAYZ_ERROR_NO_MEMORY;
    }
    u8* low = high + (width*height);
    convertToDiff(width,height,bay16,high,low);
    int highsize = FSE_compress(out+headersize,high,width*height);
    int lowsize = FSE_compress(out+highsize+headersize,low,width*height);
    //printf("uncomp 16bit: %d,highbits:%d,lowbits:%d,total:%d\n",width*height*2,highsize,lowsize,highsize+lowsize);
    free(high);
    int* head = (int*)out;
    head[0] = 0xBA7E9214; // Sig
    head[1] = width;
    head[2] = height;
    head[3] = highsize;
    head[4] = lowsize;
    // Followed by compressed data in 2 chunks...
    *bayz = (void*)out;
    return headersize+highsize+lowsize;
}

int bayz_decode16(void* bayz, int* width, int* height, unsigned short** bayer)
{
    int* in = (int*)bayz;
    if (in[0] != 0xBA7E9214) {
        return BAYZ_ERROR_BAD_SIGNATURE;
    }
    *width = in[1];
    *height = in[2];
    int bufsize = (*width) * (*height) * sizeof(u16);
    *bayer = (u16*)malloc(bufsize);  
    int size = (*width)*(*height);
    u8* high = (u8*)malloc(size*2);
    if ((*bayer==NULL)||(high==NULL)) {
        free(bayer);
        *bayer = NULL;
        free(high);
        return BAYZ_ERROR_NO_MEMORY;
    }
    u8* low = high+(size);
    int highsize = FSE_decompress(high,size,&in[5]);
    int lowsize = FSE_decompress(low,size,((u8*)(&in[5]))+highsize);
    convertFromDiff(*width,*height,*bayer,high,low);
    free(high);
    printf("bayz_decode: width=%d, height=%d, hs=%d, ls=%d, ohs=%d, ols=%d\n",*width,*height,highsize,lowsize,in[3],in[4]);
    return bufsize;
}
