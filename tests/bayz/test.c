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
#include "time.h"
#include "bayz.h"
#include "math.h"

unsigned short* read_raw_file(char* filename, int frame, int* width, int* height, int* blacklevel, char** rawheader, int* framesize)
/*
Read first frame from a RAW file
*/
{
    FILE* fh = fopen(filename,"rb");
    if (fh==NULL) return NULL;
    *rawheader = (char*)malloc(192);
    char* header = *rawheader;
    fseek(fh,-192,SEEK_END);
    int l = fread(&header[0],192,1,fh);
    short* h = (short*)header;
    *width = h[2];
    *height = h[3];
    int* i = (int*)header;
    *framesize = i[2];
    int framecount = i[3]; 
    *blacklevel = i[15];
    printf("Black: %d\n",*blacklevel); 
    int size = ((*width) * (*height));
    int size14 = (size * 14)>>3;
    unsigned short* raw14 = (unsigned short*)malloc(size14);
    if (frame>=framecount) frame = framecount-1;
    fseek(fh,frame*(*framesize),SEEK_SET);
    l = fread(&raw14[0],size14,1,fh); 
    fclose(fh);
    return raw14;
}

int test_compress16_frame(int w, int h,unsigned short* bay16,int blacklevel,int accuracy,int recovery,unsigned short** returnframe)
{
    void* bayz;
    int bloops = 10;
    int encoded = w*h*2*bloops;
    clock_t start = clock();
    while (bloops--) {
        bayz_encode16(w,h,bay16,&bayz,blacklevel,accuracy,recovery);
        free(bayz);
    }
    clock_t end = clock();
    float took = (float)(end-start)/CLOCKS_PER_SEC;
    printf("Encode speed: %d bytes took %.03f seconds. %.00f bytes/second.\n",encoded,took,(float)encoded/took);
    int e = bayz_encode16(w,h,bay16,&bayz,blacklevel,accuracy,recovery);
    printf("encode returned = %d\n",e);
    unsigned short* decodedbayer;
    int d = bayz_decode16(bayz,&w,&h,&decodedbayer,blacklevel);
    printf("decode returned = %d\n",d);
    if (d<0) return -1;
    free(bayz);
    printf("Compression ratio vs 14bit packed: %.03f%%\n",100.0f*(float)e/(float)(d)*16.0/14.0);
    /* Compare encoded and decoded */
    int same = 0;
    int diff = 0;
    int diffbelowblack = 0;
    double error = 0.0;
    int i;
    for (i=0;i<(w*h);i++) {
        int x = i%w;
        int y = i/w;
        //if (x<2) printf("%d:%d:%d:%d-%d (error=%d)\n",x,y,i,bay16[i],decodedbayer[i],bay16[i]-decodedbayer[i]);
        if (bay16[i] != decodedbayer[i]) {
            if (bay16[i]<blacklevel) diffbelowblack++;
            else diff++;
            double thiserr = fabs((((double)decodedbayer[i])/((double)bay16[i]))-1.0);
            error += thiserr;
        } else { same++; }
    }
    if (returnframe != NULL)
        *returnframe = decodedbayer;
    else
        free(decodedbayer);
    printf("Comparison: same=%d, different(>=black)=%d, different(<black)=%d,error=%f\n\n",same,diff,diffbelowblack,error);
    return diff;
}

int main(int argc, char** argv)
{
    int recovery = 14;
    int accuracy = 14;
    if (argc>3) {
        accuracy = atoi(argv[2]);
        recovery = atoi(argv[3]);
    }
    int abortOnFail = (accuracy >= 14);
    printf("Test with 100%% black frame:\n");
    unsigned short* synthFrame = (unsigned short*)calloc(256*256,2);
    int ret = test_compress16_frame(256,256,synthFrame,0,recovery,accuracy,NULL);
    if (abortOnFail && ret) return -1;
    printf("Test with 100%% white frame:\n");
    int i;
    for (i=0;i<(256*256);i++) { synthFrame[i] = (1<<14)-1; }
    ret = test_compress16_frame(256,256,synthFrame,0,recovery,accuracy,NULL);
    if (abortOnFail && ret) return -1;
    printf("Test with synthetic gradient frame:\n");
    for (i=0;i<(256*256);i++) {
        int x = i%256; int y = i>>8; int c=i%2;
        synthFrame[i] = c?x<<6:y<<6; 
    }
    ret = test_compress16_frame(256,256,synthFrame,0,recovery,accuracy,NULL);
    if (abortOnFail && ret) return -1;
    printf("Test with pseudo random frame:\n");
    // Test with pseudo random content
    for (i=0;i<(256*256);i++) {
        synthFrame[i] = rand()&0x3FFF; 
    }
    ret = test_compress16_frame(256,256,synthFrame,0,recovery,accuracy,NULL);
    if (abortOnFail && ret) return -1;
    if (argc>1) {
        printf("Test with real raw file frames:\n");
        FILE* decoded = fopen("decoded.raw","wb");
        int f;
        char* rawheader = NULL;
        for (f=0;f<20;f++) {
            int w;
            int h;
            int blacklevel;
            char* header;
            int framesize;
            unsigned short* bayer = read_raw_file(argv[1],f,&w,&h,&blacklevel,&header,&framesize);
            if (rawheader==NULL) rawheader = header;
            else free(header);
            if (bayer==NULL) {
                printf("Could not open RAW file\n");
                return -1;
            }
            printf("Width: %d, Height: %d\n",w,h);
            unsigned short* bay16;
            bay16 = bayz_convert14to16(w,h,bayer);
            free(bayer);
            unsigned short* decodedbay16;
            ret = test_compress16_frame(w,h,bay16,blacklevel,recovery,accuracy,&decodedbay16);
            bayer = bayz_convert16to14(w,h,decodedbay16); 
            free(decodedbay16);
            fwrite(bayer,(w*h*14)/8,1,decoded);
            printf("framesize %d %d %d\n",framesize,(w*h*14)/8,framesize-(w*h*14)/8);
            fwrite(bayer,framesize-((w*h*14)/8),1,decoded); // Padding
            free(bayer);
            //if (abortOnFail && ret) return -1;
            free(bay16);
        }
        // Write the updated header file to decoded
        int* i = (int*)rawheader;
        i[3] = 20;
        fwrite(rawheader,192,1,decoded);
        fclose(decoded); 
    }
    return 0;
}
