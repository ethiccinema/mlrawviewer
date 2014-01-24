/*
test.c (test for bayz.c)
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

*/

#include "stdlib.h"
#include "stdio.h"
#include "bayz.h"

unsigned short* read_raw_frame(char* filename, int frame, int* width, int* height)
/*
Read first frame from a RAW file
*/
{
    FILE* fh = fopen(filename,"rb");
    if (fh==NULL) return NULL;
    char header[192];
    fseek(fh,-192,SEEK_END);
    int l = fread(&header[0],192,1,fh);
    short* h = (short*)header;
    *width = h[2];
    *height = h[3];
    int* i = (int*)header;
    int framesize = i[2];
    int framecount = i[3]; 
    int size = ((*width) * (*height));
    int size14 = (size * 14)>>3;
    unsigned short* raw14 = (unsigned short*)malloc(size14);
    if (frame>=framecount) frame = framecount-1;
    fseek(fh,frame*framesize,SEEK_SET);
    l = fread(&raw14[0],size14,1,fh); 
    return raw14;
}
//14 2+12 4+10 6+8 8+6 10+4 12+2 14 = 14 bytes = 8 pixels

int main(int argc, char** argv)
{
    int i; 
    for (i=0;i<argc;i++) {
        printf("argument: %s\n",argv[i]);    
    }
    int f;
    for (f=0;f<20;f++) {
    int w;
    int h;
    unsigned short* bayer = read_raw_frame(argv[1],f,&w,&h);
    if (bayer==NULL) {
        printf("Could not open RAW file\n");
        return -1;
    }
    void* bayz;
    int e = bayz_encode(w,h,bayer,&bayz);
    printf("encode returned = %d\n",e);
    unsigned short* decodedbayer;
    int d = bayz_decode(bayz,&w,&h,&decodedbayer);
    printf("decode returned = %d\n",d);
    }
    return 0;
}
