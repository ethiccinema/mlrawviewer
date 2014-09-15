#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#include "lj92.h"

typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;

//#define SLOW_HUFF

typedef struct _ljp {
    u8* data;
    u8* dataend;
    int datalen;
    int scanstart;
    int ix;
    int x; // Width
    int y; // Height
    int bits; // Bit depth
    int writelen; // Write rows this long
    int skiplen; // Skip this many values after each row
    u16* linearize; // Linearization table
    int linlen;


    // Huffman table - only one supported, and probably needed
#ifdef SLOW_HUFF
    int* maxcode;
    int* mincode;
    int* valptr;
    u8* huffval;
    int* huffsize;
    int* huffcode;
#else
    u16* hufflut;
    int huffbits;
#endif
    // Parse state
    int cnt;
    u32 b;
    u16* image;
    u16* rowcache;
    u16* outrow[2];
} ljp;

static int find(ljp* self) {
    int ix = self->ix;
    u8* data = self->data;
    while (data[ix] != 0xFF && ix<(self->datalen-1)) {
        ix += 1;
    }
    ix += 2;
    if (ix>=self->datalen) return -1;
    self->ix = ix;
    return data[ix-1];
}

#define BEH(ptr) ((((int)(*&ptr))<<8)|(*(&ptr+1)))

static int parseHuff(ljp* self) {
    int ret = LJ92_ERROR_CORRUPT;
    u8* huffhead = &self->data[self->ix]; // xstruct.unpack('>HB16B',self.data[self.ix:self.ix+19])
    u8* bits = &huffhead[2];
    bits[0] = 0; // Because table starts from 1
    int hufflen = BEH(huffhead[0]);
    if ((self->ix + hufflen) >= self->datalen) return ret;
    u8* huffvals = &self->data[self->ix+19];
    int huffvalslen = hufflen - 19;
#ifdef SLOW_HUFF
    u8* huffval = calloc(hufflen - 19,sizeof(u8));
    if (huffval == NULL) return LJ92_ERROR_NO_MEMORY;
    self->huffval = huffval;
    for (int hix=0;hix<(hufflen-19);hix++) {
        huffval[hix] = self->data[self->ix+19+hix];
    }
    self->ix += hufflen;
    // Generate huffman table
    int k = 0;
    int i = 1;
    int j = 1;
    int huffsize_needed = 1;
    // First calculate how long huffsize needs to be
    while (i<=16) {
        while (j<=bits[i]) {
            huffsize_needed++;
            k = k+1;
            j = j+1;
        }
        i = i+1;
        j = 1;
    }
    // Now allocate and do it
    int* huffsize = calloc(huffsize_needed,sizeof(int));
    if (huffsize == NULL) return LJ92_ERROR_NO_MEMORY;
    self->huffsize = huffsize;
    k = 0;
    i = 1;
    j = 1;
    // First calculate how long huffsize needs to be
    int hsix = 0;
    while (i<=16) {
        while (j<=bits[i]) {
            huffsize[hsix++] = i;
            k = k+1;
            j = j+1;
        }
        i = i+1;
        j = 1;
    }
    huffsize[hsix++] = 0;
    int lastk = k;

    // Calculate the size of huffcode array
    int huffcode_needed = 0;
    k = 0;
    int code = 0;
    int si = huffsize[0];
    while (1) {
        while (huffsize[k] == si) {
            huffcode_needed++;
            code = code+1;
            k = k+1;
        }
        if (huffsize[k] == 0)
            break;
        while (huffsize[k] != si) {
            code = code << 1;
            si = si + 1;
        }
    }
    // Now fill it
    int* huffcode = calloc(huffcode_needed,sizeof(int));
    if (huffcode == NULL) return LJ92_ERROR_NO_MEMORY;
    self->huffcode = huffcode;
    int hcix = 0;
    k = 0;
    code = 0;
    si = huffsize[0];
    while (1) {
        while (huffsize[k] == si) {
            huffcode[hcix++] = code;
            code = code+1;
            k = k+1;
        }
        if (huffsize[k] == 0)
            break;
        while (huffsize[k] != si) {
            code = code << 1;
            si = si + 1;
        }
    }

    i = 0;
    j = 0;

    int* maxcode = calloc(17,sizeof(int));
    if (maxcode == NULL) return LJ92_ERROR_NO_MEMORY;
    self->maxcode = maxcode;
    int* mincode = calloc(17,sizeof(int));
    if (mincode == NULL) return LJ92_ERROR_NO_MEMORY;
    self->mincode = mincode;
    int* valptr = calloc(17,sizeof(int));
    if (valptr == NULL) return LJ92_ERROR_NO_MEMORY;
    self->valptr = valptr;

    while (1) {
        while (1) {
            i++;
            if (i>16)
                break;
            if (bits[i]!=0)
                break;
            maxcode[i] = -1;
        }
        if (i>16)
            break;
        valptr[i] = j;
        mincode[i] = huffcode[j];
        j = j+bits[i]-1;
        maxcode[i] = huffcode[j];
        j++;
    }
    free(huffsize);
    self->huffsize = NULL;
    free(huffcode);
    self->huffcode = NULL;
    ret = LJ92_ERROR_NONE;
#else
    /* Calculate huffman direct lut */
    // How many bits in the table - find highest entry
    int maxbits = 16;
    while (maxbits>0) {
        if (bits[maxbits]) break;
        maxbits--;
    }
    self->huffbits = maxbits;
    /* Now fill the lut */
    u16* hufflut = malloc((1<<maxbits) * sizeof(u16));
    if (hufflut == NULL) return LJ92_ERROR_NO_MEMORY;
    self->hufflut = hufflut;
    int i = 0;
    int hv = 0;
    int rv = 0;
    int vl = 0; // i
    int hcode;
    int bitsused = 1;
    while (i<1<<maxbits) {
        if (bitsused>maxbits) {
            break; // Done. Should never get here!
        }
        if (vl >= bits[bitsused]) {
            bitsused++;
            vl = 0;
            continue;
        }
        if (rv == 1 << (maxbits-bitsused)) {
            rv = 0;
            vl++;
            hv++;
            continue;
        }
        hcode = huffvals[hv];
        hufflut[i] = hcode<<8 | bitsused;
        //printf("%d %d %d\n",i,bitsused,hcode);
        i++;
        rv++;
    }
    ret = LJ92_ERROR_NONE;
#endif
    return ret;
}

static int parseSof3(ljp* self) {
    if (self->ix+6 >= self->datalen) return LJ92_ERROR_CORRUPT;
    self->y = BEH(self->data[self->ix+3]);
    self->x = BEH(self->data[self->ix+5]);
    self->bits = self->data[self->ix+2];
    self->ix += BEH(self->data[self->ix]);
    return LJ92_ERROR_NONE;
}

static int parseBlock(ljp* self,int marker) {
    self->ix += BEH(self->data[self->ix]);
    if (self->ix >= self->datalen) return LJ92_ERROR_CORRUPT;
    return LJ92_ERROR_NONE;
}

#ifdef SLOW_HUFF
static int nextbit(ljp* self) {
    u32 b = self->b;
    if (self->cnt == 0) {
        u8* data = &self->data[self->ix];
        u32 next = *data++;
        b = next;
        if (next == 0xff) {
            data++;
            self->ix++;
        }
        self->ix++;
        self->cnt = 8;
    }
    int bit = b >> 7;
    self->cnt--;
    self->b = (b << 1)&0xFF;
    return bit;
}

static int decode(ljp* self) {
    int i = 1;
    int code = nextbit(self);
    while (code > self->maxcode[i]) {
        i++;
        code = (code << 1) + nextbit(self);
    }
    int j = self->valptr[i];
    j = j + code - self->mincode[i];
    int value = self->huffval[j];
    return value;
}

static int receive(ljp* self,int ssss) {
    int i = 0;
    int v = 0;
    while (i != ssss) {
        i++;
        v = (v<<1) + nextbit(self);
    }
    return v;
}

static int extend(ljp* self,int v,int t) {
    int vt = 1<<(t-1);
    if (v < vt) {
        vt = (-1 << t) + 1;
        v = v + vt;
    }
    return v;
}
#endif

inline static int nextdiff(ljp* self) {
#ifdef SLOW_HUFF
    int t = decode(self);
    int diff = receive(self,t);
    diff = extend(self,diff,t);
#else
    u32 b = self->b;
    int cnt = self->cnt;
    int huffbits = self->huffbits;
    int ix = self->ix;
    int next;
    while (cnt < huffbits) {
        next = *(u16*)&self->data[ix];
        int one = next&0xFF;
        int two = next>>8;
        b = (b<<16)|(one<<8)|two;
        cnt += 16;
        ix += 2;
        if (one==0xFF) {
            //printf("%x %x %x %x %d\n",one,two,b,b>>8,cnt);
            b >>= 8;
            cnt -= 8;
        } else if (two==0xFF) ix++;
    }
    int index = b >> (cnt - huffbits);
    u16 ssssused = self->hufflut[index];
    int usedbits = ssssused&0xFF;
    int t = ssssused>>8;
    cnt -= usedbits;
    int keepbitsmask = (1 << cnt)-1;
    b &= keepbitsmask;
    while (cnt < t) {
        next = *(u16*)&self->data[ix];
        int one = next&0xFF;
        int two = next>>8;
        b = (b<<16)|(one<<8)|two;
        cnt += 16;
        ix += 2;
        if (one==0xFF) {
            b >>= 8;
            cnt -= 8;
        } else if (two==0xFF) ix++;
    }
    cnt -= t;
    int diff = b >> cnt;
    int vt = 1<<(t-1);
    if (diff < vt) {
        vt = (-1 << t) + 1;
        diff += vt;
    }
    keepbitsmask = (1 << cnt)-1;
    self->b = b & keepbitsmask;
    self->cnt = cnt;
    self->ix = ix;
    //printf("%d %d\n",t,diff);
#endif
    return diff;
}

static int parsePred6(ljp* self) {
    int ret = LJ92_ERROR_CORRUPT;
    self->ix = self->scanstart;
    int compcount = self->data[self->ix+2];
    self->ix += BEH(self->data[self->ix]);
    self->cnt = 0;
    self->b = 0;
    // Now need to decode huffman coded values
    int c = 0;
    int pixels = self->y * self->x;
    u16* out = self->image;

    // First pixel predicted from base value
    int diff;
    int Px;
    int col = 0;
    int row = 0;
    int left = 0;

    // First pixel
    diff = nextdiff(self);
    Px = 1 << (self->bits-1);
    left = Px + diff;
    out[c++] = left;
    if (++col==self->x) {
        col = 0;
        row++;
    }
    if (self->ix >= self->datalen) return ret;

    int rowcount = self->x-1;
    while (rowcount--) {
        diff = nextdiff(self);
        Px = left;
        left = Px + diff;
        out[c++] = left;
        if (self->ix >= self->datalen) return ret;
    }
    col = 0;
    row++;

    while (c<pixels) {
        diff = nextdiff(self);
        Px = out[c-self->x]; // Use value above for first pixel in row
        left = Px + diff;
        //printf("%d %d %d\n",c,diff,left);
        out[c++] = left;
        if (self->ix >= self->datalen) break;
        rowcount = self->x-1;
        u16* outprev = &out[c-self->x];
        while (rowcount--) {
            diff = nextdiff(self);
            Px = outprev[0] + ((left - outprev[-1])>>1);
            left = Px + diff;
            //printf("%d %d %d\n",c,diff,left);
            out[c++] = left;
            outprev++;
        }
        if (self->ix >= self->datalen) break;
    }
    if (c >= pixels) ret = LJ92_ERROR_NONE;
    return ret;
}

static int parseScan(ljp* self) {
    int ret = LJ92_ERROR_CORRUPT;
    self->ix = self->scanstart;
    int compcount = self->data[self->ix+2];
    int pred = self->data[self->ix+3+2*compcount];
    if (pred<0 || pred>7) return ret;
    //if (pred==6) return parsePred6(self); // Fast path
    self->ix += BEH(self->data[self->ix]);
    self->cnt = 0;
    self->b = 0;
    int write = self->writelen;
    // Now need to decode huffman coded values
    int c = 0;
    int pixels = self->y * self->x;
    u16* out = self->image;
    u16* outlast = out - self->x; // Shouldn't use until row 2
    u16* thisrow = self->outrow[0];
    u16* lastrow = self->outrow[1];

    // First pixel predicted from base value
    int diff;
    int Px;
    int col = 0;
    int row = 0;
    int left = 0;
    while (c<pixels) {
        diff = nextdiff(self);
        if ((col==0)&&(row==0)) {
            Px = 1 << (self->bits-1);
        } else if (row==0) {
            Px = left;
        } else if (col==0) {
            Px = lastrow[col]; // Use value above for first pixel in row
        } else {
            switch (pred) {
            case 0:
                Px = 0; break; // No prediction... should not be used
            case 1:
                Px = left; break;
            case 2:
                Px = lastrow[col]; break;
            case 3:
                Px = lastrow[col-1];break;
            case 4:
                Px = left + lastrow[col] - lastrow[col-1];break;
            case 5:
                Px = left + (lastrow[col] - lastrow[col-1])>>1;break;
            case 6:
                Px = lastrow[col] + ((left - lastrow[col-1])>>1);break;
            case 7:
                Px = (left + lastrow[col])>>1;break;
            }
        }
        left = Px + diff;
        //printf("%d %d %d\n",c,diff,left);
        out[c] = left;
        c++;
        thisrow[col] = left;
        if (--write==0) {
            out += self->skiplen;
            write = self->writelen;
        }
        if (++col==self->x) {
            col = 0;
            row++;
            u16* temprow = lastrow;
            lastrow = thisrow;
            thisrow = temprow;
        }
        if (self->ix >= self->datalen+2) break;
    }
    if (c >= pixels) ret = LJ92_ERROR_NONE;
    return ret;
}

static int parseImage(ljp* self) {
    int ret = LJ92_ERROR_NONE;
    while (1) {
        int nextMarker = find(self);
        if (nextMarker == 0xc4)
            ret = parseHuff(self);
        else if (nextMarker == 0xc3)
            ret = parseSof3(self);
        else if (nextMarker == 0xfe)// Comment
            ret = parseBlock(self,nextMarker);
        else if (nextMarker == 0xd9) // End of image
            break;
        else if (nextMarker == 0xda) {
            self->scanstart = self->ix;
            ret = LJ92_ERROR_NONE;
            break;
        } else if (nextMarker == -1) {
            ret = LJ92_ERROR_CORRUPT;
            break;
        } else
            ret = parseBlock(self,nextMarker);
        if (ret != LJ92_ERROR_NONE) break;
    }
    return ret;
}

static int findSoI(ljp* self) {
    int ret = LJ92_ERROR_CORRUPT;
    if (find(self)==0xd8)
        ret = parseImage(self);
    return ret;
}

static void free_memory(ljp* self) {
#ifdef SLOW_HUFF
    free(self->maxcode);
    self->maxcode = NULL;
    free(self->mincode);
    self->mincode = NULL;
    free(self->valptr);
    self->valptr = NULL;
    free(self->huffval);
    self->huffval = NULL;
    free(self->huffsize);
    self->huffsize = NULL;
    free(self->huffcode);
    self->huffcode = NULL;
#else
    free(self->hufflut);
    self->hufflut = NULL;
#endif
    free(self->rowcache);
    self->rowcache = NULL;
}

int lj92_open(lj92* lj,
              char* data, int datalen,
              int* width,int* height, int* bitdepth) {
    ljp* self = (ljp*)calloc(sizeof(ljp),1);
    if (self==NULL) return LJ92_ERROR_NO_MEMORY;

    self->data = (u8*)data;
    self->dataend = self->data + datalen;
    self->datalen = datalen;
#ifdef SLOW_HUFF
#else
    u16* hufflut;
    int huffbits;
#endif

    int ret = findSoI(self);

    if (ret == LJ92_ERROR_NONE) {
        u16* rowcache = calloc(self->x * 2,sizeof(u16));
        if (rowcache == NULL) ret = LJ92_ERROR_NO_MEMORY;
        else {
            self->rowcache = rowcache;
            self->outrow[0] = rowcache;
            self->outrow[1] = &rowcache[self->x];
        }
    }

    if (ret != LJ92_ERROR_NONE) { // Failed, clean up
        *lj = NULL;
        free_memory(self);
        free(self);
    } else {
        *width = self->x;
        *height = self->y;
        *bitdepth = self->bits;
        *lj = self;
    }
    return ret;
}

int lj92_decode(lj92 lj,
                uint16_t* target,int writeLength, int skipLength,
                uint16_t* linearize,int linearizeLength) {
    int ret = LJ92_ERROR_NONE;
    ljp* self = lj;
    if (self == NULL) return LJ92_ERROR_BAD_HANDLE;
    self->image = target;
    self->writelen = writeLength;
    self->skiplen = skipLength;
    self->linearize = linearize;
    self->linlen = linearizeLength;
    ret = parseScan(self);
    return ret;
}

void lj92_close(lj92 lj) {
    ljp* self = lj;
    if (self != NULL)
        free_memory(self);
    free(self);
}

#ifdef TEST_DECODER
void main(int argc,char** argv) {
    char* first;
    char* second;
    if (argc<2) {
        printf("Please provide 1 (or 2 identical sized) lossless JPEG file(s)\n");
        return;
    }
    if (argc>=2) first = argv[1];
    if (argc>=3) second = argv[2];
    else second = first;

    // Read in filenames to memory
    FILE* datafile = fopen(argv[1],"r");
    fseek(datafile,0,SEEK_END);
    long length = ftell(datafile);
    fseek(datafile,0,SEEK_SET);
    printf("Length of file=%lu\n",length);
    char* data = malloc(length);
    int readlen = fread(data,1,length,datafile);
    printf("readlen=%d\n",readlen);
    fclose(datafile);

    datafile = fopen(argv[2],"r");
    fseek(datafile,0,SEEK_END);
    length = ftell(datafile);
    fseek(datafile,0,SEEK_SET);
    printf("Length of file=%lu\n",length);
    char* data2 = malloc(length);
    int readlen2 = fread(data2,1,length,datafile);
    printf("readlen=%d\n",readlen2);
    fclose(datafile);

    // Now process the data
    int width,height,bitdepth;
    int width2,height2,bitdepth2;
    lj92 ljp;
    lj92 ljp2;
    int ret = lj92_open(&ljp,data,readlen,&width,&height,&bitdepth);
    printf("lj92_open returned %d width=%d, height=%d, bitdepth=%d\n",ret,width,height,bitdepth);
    ret = lj92_open(&ljp2,data2,readlen2,&width2,&height2,&bitdepth2);
    if ((width!=width2) && (height!=height2)) {
        printf("Files do not have identical frame size %dx%d vs %dx%d\n",width,height,width2,height2);
        return;
    }
    printf("lj92_open returned %d width=%d, height=%d, bitdepth=%d\n",ret,width2,height2,bitdepth2);
    printf("Creating frame %dx%d\n",width,height*2);
    uint16_t* image = (uint16_t*)calloc(width*height*2,sizeof(uint16_t));
    for (int loop=0;loop<50;loop++) {
        ret = lj92_decode(ljp,image,width/2,width/2,NULL,0);
        if (ret != LJ92_ERROR_NONE) {
            printf("lj92_decode returned %d\n",ret);
        }
        ret = lj92_decode(ljp2,image+width/2,width/2,width/2,NULL,0);
        if (ret != LJ92_ERROR_NONE) {
            printf("lj92_decode returned %d\n",ret);
        }
    }

    // Convert to big endian 16bit for output as PGM file
    for (int i=0;i<(width*height*2);i++) {
        image[i] = (image[i]>>8)|((image[i]&0xFF)<<8);
    }
    FILE* rafile = fopen("dump.pgm","w");
    fprintf(rafile,"P5 %d %d 4096\n",width,height*2);
    fwrite(image,2,width*height*2,rafile);
    fclose(rafile);
    free(image);
    free(data);
    free(data2);

    // Finish
    lj92_close(ljp);
    lj92_close(ljp2);
}
#endif
