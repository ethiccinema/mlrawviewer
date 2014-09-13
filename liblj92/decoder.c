#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;

#define FAST_HUFF

typedef struct _parser {
    u8* data;
    int datalen;
    int ix;
    int x; // Width
    int y; // Height
    int bits; // Bit depth

    // Huffman table - only one supported, and probably needed
#ifndef FAST_HUFF
    int* maxcode;
    int* mincode;
    int* valptr;
    u8* huffval;
#else
    u16* hufflut;
    int huffbits;
#endif
    // Parse state
    int cnt;
    u32 b;
    u16* image;
} ljp;

int find(ljp* self) {
    int ix = self->ix;
    u8* data = self->data;
    while (data[ix] != 0xFF && ix<(self->datalen-1)) {
        ix += 1;
    }
    ix += 2;
    self->ix = ix;
    return data[ix-1];
}

#define BEH(ptr) ((((int)(*&ptr))<<8)|(*(&ptr+1)))

void parseHuff(ljp* self) {
    u8* huffhead = &self->data[self->ix]; // xstruct.unpack('>HB16B',self.data[self.ix:self.ix+19])
    u8* bits = &huffhead[2];
    bits[0] = 0; // Because table starts from 1
    int hufflen = BEH(huffhead[0]);
    u8* huffval = calloc(hufflen - 19,sizeof(u8));
    u8* huffvals = &self->data[self->ix+19];
    int huffvalslen = hufflen - 19;
#ifndef FAST_HUFF
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
    int* mincode = calloc(17,sizeof(int));
    int* valptr = calloc(17,sizeof(int));
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
    self->maxcode = maxcode;
    self->mincode = mincode;
    self->valptr = valptr;
    self->huffval = huffval;
    free(huffsize);
    free(huffcode);

#else
    /* Calculate huffman direct lut */
    // How many bits in the table - find highest entry
    int maxbits = 16;
    while (maxbits>0) {
        if (bits[maxbits]) break;
        maxbits--;
    }
    /* Now fill the lut */
    u16* hufflut = malloc((1<<maxbits) * sizeof(u16));
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
    self->huffbits = maxbits;
    self->hufflut = hufflut;
#endif
}

void parseSof3(ljp* self) {
    self->y = BEH(self->data[self->ix+3]);
    self->x = BEH(self->data[self->ix+5]);
    self->bits = self->data[self->ix+2];
    self->ix += BEH(self->data[self->ix]);
}

void parseBlock(ljp* self,int marker) {
    self->ix += BEH(self->data[self->ix]);
}

#ifndef FAST_HUFF
int nextbit(ljp* self) {
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

int decode(ljp* self) {
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

int receive(ljp* self,int ssss) {
    int i = 0;
    int v = 0;
    while (i != ssss) {
        i++;
        v = (v<<1) + nextbit(self);
    }
    return v;
}

int extend(ljp* self,int v,int t) {
    int vt = 1<<(t-1);
    if (v < vt) {
        vt = (-1 << t) + 1;
        v = v + vt;
    }
    return v;
}
#endif

int nextdiff(ljp* self) {
#ifndef FAST_HUFF
    int t = decode(self);
    int diff = receive(self,t);
    diff = extend(self,diff,t);
#else
    while (self->cnt < self->huffbits) {
        int next = self->data[self->ix++];
        self->b = (self->b << 8)|next;
        self->cnt += 8;
        if (next==0xFF) self->ix++;
    }
    int index = self->b >> (self->cnt - self->huffbits);
    u16 ssssused = self->hufflut[index];
    int usedbits = ssssused&0xFF;
    int t = ssssused>>8;
    int keepbitsmask = (1 << (self->cnt - usedbits))-1;
    self->b &= keepbitsmask;
    self->cnt -= usedbits;
    while (self->cnt < t) {
        int next = self->data[self->ix++];
        self->b = (self->b << 8)|next;
        self->cnt += 8;
        if (next==0xFF) self->ix++;
    }
    int diff = self->b >> (self->cnt - t);
    keepbitsmask = (1 << (self->cnt - t))-1;
    self->b &= keepbitsmask;
    self->cnt -= t;
    int vt = 1<<(t-1);
    if (diff < vt) {
        vt = (-1 << t) + 1;
        diff += vt;
    }
    //printf("%d %d\n",t,diff);
#endif
    return diff;
}

void parseScan(ljp* self) {
    int compcount = self->data[self->ix+2];
    int pred = self->data[self->ix+3+2*compcount];
    self->ix += BEH(self->data[self->ix]);
    self->cnt = 0;
    self->b = 0;
    // Now need to decode huffman coded values
    int c = 0;
    int pixels = self->y * self->x;
    u16* out = malloc(pixels*sizeof(u16));

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
            Px = out[c-self->x]; // Use value above for first pixel in row
        } else {
            switch (pred) {
            case 0:
                Px = 0; break; // No prediction... should not be used
            case 1:
                Px = left; break;
            case 2:
                Px = out[c-self->x]; break;
            case 3:
                Px = out[c-self->x-1];break;
            case 4:
                Px = left + out[c-self->x] - out[c-self->x-1];break;
            case 5:
                Px = left + (out[c-self->x] - out[c-self->x-1])>>1;break;
            case 6:
                Px = out[c-self->x] + ((left - out[c-self->x-1])>>1);break;
            case 7:
                Px = (left + out[c-self->x])>>1;break;
            }
        }
        left = Px + diff;
        //printf("%d %d %d\n",c,diff,left);
        out[c] = left;
        c++;
        if (++col==self->x) {
            col = 0;
            row++;
        }
    }
    self->image = out;
}

int parseImage(ljp* self) {
    //printf("Parsing image\n");
    while (1) {
        int nextMarker = find(self);
        if (nextMarker == 0xc4)
            parseHuff(self);
        else if (nextMarker == 0xc3)
            parseSof3(self);
        else if (nextMarker == 0xfe)// Comment
            parseBlock(self,nextMarker);
        else if (nextMarker == 0xd9) // End of image
            break;
        else if (nextMarker == 0xda) {
            parseScan(self);
            break;
        }
        else
            parseBlock(self,nextMarker);
    }
    //printf("Parsing image complete\n");
    return 0;
}

int findSoI(ljp* self) {
    if (find(self)==0xd8) return parseImage(self);
}

u16* parse(char* data,int datalen,int* width,int* height) {
    ljp self;
    self.ix = 0;
    self.data = (u8*)data;
    self.datalen = datalen;
    findSoI(&self);
    *width = self.x;
    *height = self.y;
    return self.image;
}

void main(int argc,char** argv) {
    // Read in filename to memory
    FILE* datafile = fopen(argv[1],"r");
    fseek(datafile,0,SEEK_END);
    long length = ftell(datafile);
    fseek(datafile,0,SEEK_SET);
    printf("Length of file=%lu\n",length);
    char* data = malloc(length);
    int readlen = fread(data,1,length,datafile);
    printf("readlen=%d\n",readlen);
    fclose(datafile);

    // Now process the data
    int width,height;
    u16* image = NULL;
    for (int loop=0;loop<100;loop++) {
        free(image);
        image = parse(data,length,&width,&height);
    }
    for (int i=0;i<(width*height);i++) {
        image[i] = (image[i]>>8)|((image[i]&0xFF)<<8);
    }
    FILE* rafile = fopen("dump.pgm","w");
    fprintf(rafile,"P5 %d %d 4096\n",width,height);
    fwrite(image,2,width*height,rafile);
    fclose(rafile);
}
