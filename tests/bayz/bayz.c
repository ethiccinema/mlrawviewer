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


#include <stdlib.h>
#include <stdio.h>
#include <string.h>
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

static u16* raw16to14(int width, int height, u16* bay16, u16* bay14) 
{
    u16* o = bay14;
    u16* i = bay16;
    int blocks = (width*height)/8;
    while (blocks--) {
       *o++ = (i[0]<<2)|((i[1]>>12)&0x3);
       //*o++ = (i[0]>>2)&0x3FFF;
       *o++ = ((i[1]&0xFFF)<<4)|((i[2]>>10)&0xF);
       //*o++ = ((i[0]&0x3)<<12)|((i[1]>>4)&0xFFF); 
       *o++ = ((i[2]&0x3FF)<<6)|((i[3]>>8)&0x3F);
       //*o++ = ((i[1]&0xF)<<10)|((i[2]>>6)&0x3FF); 
       *o++ = ((i[3]&0xFF)<<8)|((i[4]>>6)&0xFF);
       //*o++ = ((i[2]&0x3F)<<8)|((i[3]>>8)&0xFF); 
       *o++ = ((i[4]&0x3F)<<10)|((i[5]>>4)&0x3FF);
       //*o++ = ((i[3]&0xFF)<<6)|((i[4]>>10)&0x3F); 
       *o++ = ((i[5]&0xF)<<12)|((i[6]>>2)&0xFFF);
       //*o++ = ((i[4]&0x3FF)<<4)|((i[5]>>12)&0xF); 
       *o++ = ((i[6]&0x3)<<14)|(i[7]&0x3FFF);
       i += 8;
    } 
    return bay14;
}


u16 encode(int val)
{
    u16 encoded = 0;

    if(1)
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
    
    if (1)
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

u16 combine_bytes(u8 *high, u8 *low)
{
    return (*high << 8)|(*low & 0xFF);
}

int quantize(int level,int last_level,int black, int accuracy, int recovery)
{
/*
Goal of this is to quantize the deltas to approach 
correct values using fewer bits.
In bright areas, accuracy can be lower
In dark areas, accuracy must be higher
Small deltas (other than zero) should not be rounded to zero
in order to try to match the original data
*/
    if (accuracy >= 14) return level - last_level;
    int brightness = level - black;
    brightness = brightness<0?0:brightness;
    int diff = level - last_level;
    int bmag = 32 - __builtin_clz(brightness) - accuracy;
    int dmag = 32 - __builtin_clz(diff<0?-diff:diff) - recovery;
    int mag;
    mag = bmag>dmag?dmag:bmag;
    mag = mag<0?0:mag;
    int mask = ((1<<mag)-1);
    //int error = (diff & mask);
    int mdiff;
    if (diff < 0) {
        //error = -((-diff )&mask);
        mdiff = -(((-diff)+(mask>>1))&(~mask));
    } else {
        mdiff = (diff + (mask>>1))&(~mask);
    }
    //printf("\nlevel=%d,bn=%d,diff=%d(%x),bmag=%d,dmag=%d,mag=%d,mask=%x,mdiff=%d(%x),err=%d,newlevel=%d\n",level,brightness,diff,diff,bmag,dmag,mag,mask,mdiff,mdiff,mdiff-diff,last_level+mdiff);
    //printf("g=%d,last_g=%d,brightness=%d,mag=%d,mask=%x,diff=%d,diffmask=%d,error=%d(%x),lg=%d\n",level,last_level,brightness,mag,mask,diff,error,diff-error,diff-error,last_level+(diff - error));
    //diff = diff - error;
    return mdiff;
}

#define CLIPBLACK14(val) (((val)<(black))?(black):((val)&0x3FFF))

static void convertToDiff(int width, int height, u16* raw16, u8* high, u8* low, u8* shape,int black,int accuracy,int recovery)
/*
Low and high parts encode per pixel deltas.
Either exactly in lossless mode, or quantized in lossy mode
Shape can be used to encode broad (low frequency) shape with 
less than 1 bit per pixel using slopes. Shape 
encoding format is a current delta (for both colour values in a row)
value to apply to current baseline. 
For most samples that delta should be a repeat of the previous one.
If low & high are totally zero, a rough image should still be seen
*/
{
    u16* r = raw16;  
    int y,x;
    for (y=0;y<height;) {
        int last_h = black;
        int last_g = black;
        // First 2 columns encode delta downwards
        if (y>0) last_g = CLIPBLACK14(r[-width]);
        if (y>1) last_h = CLIPBLACK14(r[-(width<<1)]);
        for (x=0;x<width;x+=2) {
            int h = CLIPBLACK14(r[x]);
            int g = CLIPBLACK14(r[x+1]);
            int gd,hd;
            if (x==0) {
                // First 2 columns must be 100% correct for predicting lower columns
                gd = g - last_g;
                hd = h - last_h; 
            } else {
                gd = quantize(g,last_g,black,accuracy,recovery);
                hd = quantize(h,last_h,black,accuracy,recovery);
            }
            //u16 gout = encode(gd);
            //if (x<2) {
            //    printf("%d:%d,lg=%d,g=%d,gd=%d,encode(gd)=%d\n",x,y,last_g,g,gd,encode(gd));
            //}
            //printf("%d->%d->%x(%d)->%x,",last_g,g,gd,gd,gout);
            split_bytes(encode(hd), &high[x], &low[x]);
            split_bytes(encode(gd), &high[x+1], &low[x+1]);
            shape[x] = 0;
            shape[x+1] = 0;
            last_h = CLIPBLACK14(last_h + hd);
            last_g = CLIPBLACK14(last_g + gd);            
        }
        //printf("\n");
        y++; high += width; low += width; r += width; shape += width;
        last_h = black;
        last_g = black;
        // First 2 columns encode delta downwards
        if (y>0) last_g = CLIPBLACK14(r[-width+1]);
        if (y>1) last_h = CLIPBLACK14(r[-(width<<1)+1]);
        for (x=0;x<width;x+=2) {
            int g = CLIPBLACK14(r[x]);
            int h = CLIPBLACK14(r[x+1]);
            int gd,hd;
            if (x==0) {
                // First 2 columns must be 100% correct for predicting lower columns
                gd = g - last_g;
                hd = h - last_h; 
            } else {
                gd = quantize(g,last_g,black,accuracy,recovery);
                hd = quantize(h,last_h,black,accuracy,recovery);
            }
            //if (x<2) {
            //    printf("%d:%d,lg=%d,g=%d,gd=%d,encode(gd)=%d\n",x,y,last_g,g,gd,encode(gd));
            //}
            split_bytes(encode(gd), &high[x], &low[x]);
            split_bytes(encode(hd), &high[x+1], &low[x+1]);
            shape[x] = 0;
            shape[x+1] = 0;
            last_h = CLIPBLACK14(last_h + hd);
            last_g = CLIPBLACK14(last_g + gd);            
        }
        y++; high += width; low += width; r += width; shape += width;
    }
}

static void convertFromDiff(int width, int height, u16* raw16, u8* high, u8* low, u8* shape, int black)
{
/*
Invert convertToDiff
*/
    u16* r = raw16;  
    int y,x;
    for (y=0;y<height;) {
        int last_g = black;
        int last_h = black;
        // First 2 columns encode delta downwards
        if (y>0) last_g = CLIPBLACK14(r[-width]);
        if (y>1) last_h = CLIPBLACK14(r[-(width<<1)]);
        for (x=0;x<width;x+=2) {
            int dh = decode(combine_bytes(&high[x],&low[x]));
            int dg = decode(combine_bytes(&high[x+1],&low[x+1]));
            u16 h = CLIPBLACK14(last_h + dh);
            u16 g = CLIPBLACK14(last_g + dg);
            r[x] = h;
            r[x+1] = g;
            last_h = h;
            last_g = g; 
        }
        y++; r += width; high += width; low += width;
        last_g = black;
        last_h = black;
        // First 2 columns encode delta downwards
        if (y>0) last_g = CLIPBLACK14(r[-width+1]);
        if (y>1) last_h = CLIPBLACK14(r[-(width<<1)+1]);
        for (x=0;x<width;x+=2) {
            int dg = decode(combine_bytes(&high[x],&low[x]));
            int dh = decode(combine_bytes(&high[x+1],&low[x+1]));
            u16 g = CLIPBLACK14(last_g + dg);
            u16 h = CLIPBLACK14(last_h + dh);
            r[x] = g;
            r[x+1] = h;
            last_g = g; 
            last_h = h;
        }
        y++; r += width; high += width; low += width;
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

unsigned short* bayz_convert16to14(int width, int height, unsigned short* bay16)
{
    u16* bay14 = (u16*)malloc((width*height*14)/8); 
    if (bay14 != NULL) {
        raw16to14(width,height,bay16,bay14);
    }
    return bay14;
}


int bayz_encode14(int width, int height, unsigned short* bay14, void** bayz,int blacklevel,int accuracy,int recovery)
{
    u16* bay16 = (u16*)malloc(width*height*sizeof(u16)); 
    raw14to16(width,height,bay14,bay16);
    int ret = bayz_encode16(width,height,bay16,bayz,blacklevel,accuracy,recovery);
    free(bay16);
    return ret;
}

static histogram(u8* source,int count)
{
    int i=count;
    int bins[256];
    memset(bins,0,sizeof(bins));
    while(i--) {
        bins[*source++]++; 
    }
    for (i=0;i<256;i++) {
        printf("%d:%d(%.02f%%)\t",i,bins[i],100.0f*((float)bins[i])/((float)count));
        if ((i+1)%8==0) printf("\n");
    }
}



int bayz_encode16(int width, int height, unsigned short* bay16, void** bayz,int blacklevel,int accuracy,int recovery)
{
    //printf("bayz_encode: width=%d, height=%d\n",width,height);
    const int headersize = 6*sizeof(int);
    u8* high = (u8*)malloc(width*height*3);
    int fsesize = FSE_compressBound(width*height)*3+headersize;
    void* out = (void*)malloc(fsesize);
    if ((high==NULL)||(out==NULL)) {
        free(high);
        free(out);
        *bayz = NULL;
        return BAYZ_ERROR_NO_MEMORY;
    }
    u8* low = high + (width*height);
    u8* shape = low + (width*height);
    convertToDiff(width,height,bay16,high,low,shape,blacklevel,accuracy,recovery);
    /*printf("Histogram (high):\n");
    histogram(high,width*height);
    printf("Histogram (low):\n");
    histogram(low,width*height);
    printf("Histogram (shape):\n");
    histogram(shape,width*height);*/
    int highsize = FSE_compress(out+headersize,high,width*height);
    int lowsize = FSE_compress(out+highsize+headersize,low,width*height);
    int shapesize = FSE_compress(out+highsize+lowsize+headersize,shape,width*height);
    //printf("uncomp 16bit: %d,highbits:%d,lowbits:%d,shapebits:%d,total:%d\n",width*height*2,highsize,lowsize,shapesize,highsize+lowsize+shapesize);
    free(high);
    int* head = (int*)out;
    head[0] = 0xBA7E9214; // Sig
    head[1] = width;
    head[2] = height;
    head[3] = highsize;
    head[4] = lowsize;
    head[5] = shapesize;
    // Followed by compressed data in 2 chunks...
    *bayz = (void*)out;
    return headersize+highsize+lowsize+shapesize;
}

int bayz_decode16(void* bayz, int* width, int* height, unsigned short** bayer,int blacklevel)
{
    int* in = (int*)bayz;
    *bayer = NULL;
    if (in[0] != 0xBA7E9214) {
        return BAYZ_ERROR_BAD_SIGNATURE;
    }
    *width = in[1];
    *height = in[2];
    int bufsize = (*width) * (*height) * sizeof(u16);
    *bayer = (u16*)malloc(bufsize);  
    int size = (*width)*(*height);
    u8* high = (u8*)malloc(size*3);
    if ((*bayer==NULL)||(high==NULL)) {
        free(*bayer);
        *bayer = NULL;
        free(high);
        return BAYZ_ERROR_NO_MEMORY;
    }
    u8* low = high+(size);
    u8* shape = low+(size);
    int highsize = FSE_decompress(high,size,&in[6]);
    if (highsize != in[3]) { free(high); free(*bayer); *bayer=NULL; return BAYZ_ERROR_CORRUPT_HIGH; }
    int lowsize = FSE_decompress(low,size,((u8*)(&in[6]))+highsize);
    if (lowsize != in[4]) { free(high); free(*bayer); *bayer=NULL; return BAYZ_ERROR_CORRUPT_LOW; }
    int shapesize = FSE_decompress(shape,size,((u8*)(&in[6]))+highsize+lowsize);
    if (shapesize != in[5]) { free(high); free(*bayer); *bayer=NULL; return BAYZ_ERROR_CORRUPT_SHAPE; }
    convertFromDiff(*width,*height,*bayer,high,low,shape,blacklevel);
    free(high);
    //printf("bayz_decode: width=%d, height=%d, hs=%d, ls=%d, ohs=%d, ols=%d\n",*width,*height,highsize,lowsize,in[3],in[4]);
    return bufsize;
}
