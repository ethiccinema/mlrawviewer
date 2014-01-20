#include <Python.h>

void demosaic(
    float** rawData,    /* holds preprocessed pixel values, rawData[i][j] corresponds to the ith row and jth column */
    float** red,        /* the interpolated red plane */
    float** green,      /* the interpolated green plane */
    float** blue,       /* the interpolated blue plane */
    int winx, int winy, /* crop window for demosaicing */
    int winw, int winh
);

static PyObject*
bitunpack_demosaic14(PyObject* self, PyObject *args)
{
    unsigned const char* input = 0;
    int length = 0;
    int width = 0;
    int height = 0;
    int black = 2000;
    int byteSwap = 0;
    if (!PyArg_ParseTuple(args, "t#iiii", &input, &length, &width, &height, &black, &byteSwap))
        return NULL;
    //printf("width %d height %d\n",width,height);
    PyObject* ba = PyByteArray_FromStringAndSize("",0);
    int elements = length*8/14;
    PyByteArray_Resize(ba,elements*12); // Demosaiced as RGB 32bit float data

    // Convert 14bit packed to data to 32bit RAW float data, not demosaiced
    float* raw = (float*)malloc(elements*sizeof(float));
    float** rrows = (float**)malloc(height*sizeof(float*));
    int rr = 0;
    for (;rr<height;rr++) {
        rrows[rr] = raw + rr*width;
    }

    int i = 0;
    int sparebits = 0;
    unsigned int acc = 0;
    unsigned int out = 0;
    short unsigned int* read = (short unsigned int*)input;
    float* write = raw;
    //printf("Decoding frame\n");

    int min = 70000;
    int max = 0;
    float imaxf=0.0f;
    float iminf=999999999.0f;
    while (i<elements) {
        if (sparebits<14) {
            short unsigned int r = *read++;
            if (byteSwap) 
                r = (r&0xFF00)>>8 | ((r&0x00FF)<<8);
            acc |= r;
            sparebits += 2;
            out = (acc>>sparebits)&0x3FFF;
        } else {
            sparebits += 2;
            out = (acc>>sparebits)&0x3FFF;
            sparebits = 0;
            acc = 0;
        }
        //if (out<min) min=out;
        //if (out>max) max=out;
        if (out==0) { // Dead pixel masking
            *write++ = *(write-2);
        } else {
            int ival = out-black;
            // To avoid artifacts from demosaicing at low levels
            ival += 15.0;
            if (ival<15) ival=15; // Don't want log2(0)

            float val = (float)ival;//64.0*log2((float)ival);
            *write++ = val;
        }
        //if (val<iminf) iminf = val;
        //if (val>imaxf) imaxf = val;
        acc = (acc&((1<<sparebits)-1))<<16;
        i++;
    }

    // Now demosaic with CPU
    float* red = malloc(elements*sizeof(float));
    float** redrows = (float**)malloc(height*sizeof(float*));
    for (rr=0;rr<height;rr++) {
        redrows[rr] = red + rr*width;
    }
    float* green = malloc(elements*sizeof(float));
    float** greenrows = (float**)malloc(height*sizeof(float*));
    for (rr=0;rr<height;rr++) {
        greenrows[rr] = green + rr*width;
    }
    float* blue = malloc(elements*sizeof(float));
    float** bluerows = (float**)malloc(height*sizeof(float*));
    for (rr=0;rr<height;rr++) {
        bluerows[rr] = blue + rr*width;
    }

    demosaic(rrows,redrows,greenrows,bluerows,0,0,width,height);

    // Now interleave into final RGB float array
    float* outptr = (float*)PyByteArray_AS_STRING(ba);
    float* rptr = red;
    float* gptr = green;
    float* bptr = blue;
    float maxf=0.0f;
    float minf=999999999.0f;
    for (rr=0;rr<elements;rr++) {
           *outptr++ = (*rptr++);
           *outptr++ = (*gptr++);
           *outptr++ = (*bptr++);
    /*       float t = (*rptr++)/64.0;//exp2((*rptr++)/2048.0f);
           if (t<1.0f) t = 1.0f;
           float l = exp2(t)-15.0f; // Invert earlier offset
           if (l<0.0f) l = 0.0f;
           *outptr++ = l;

           t = (*gptr++)/64.0;//exp2((*gptr++)/2048.0f);
           if (t<1.0f) t = 1.0f;
           l = exp2(t)-15.0f;
           if (l<0.0f) l = 0.0f;
           *outptr++ = l;

           t = (*bptr++)/64.0;//exp2((*bptr++)/2048.0f);
           if (t<1.0f) t = 1.0f;
           l = exp2(t)-15.0f;
           if (l<0.0f) l = 0.0f;
           *outptr++ = l;*/
    }
    //printf("min=%d,max=%d,iminf=%f,imaxf=%f,minf=%f, maxf=%f\n",min,max,iminf,imaxf,minf,maxf);
    free(raw);
    free(rrows);
    free(red);
    free(redrows);
    free(green);
    free(greenrows);
    free(blue);
    free(bluerows);

    return ba;
}

static PyObject*
bitunpack_demosaic16(PyObject* self, PyObject *args)
{
    unsigned const char* input = 0;
    int length = 0;
    int width = 0;
    int height = 0;
    int black = 2000;
    int byteSwap = 0;
    if (!PyArg_ParseTuple(args, "t#iiii", &input, &length, &width, &height, &black, &byteSwap))
        return NULL;
    //printf("width %d height %d\n",width,height);
    PyObject* ba = PyByteArray_FromStringAndSize("",0);
    int elements = length/2;
    PyByteArray_Resize(ba,elements*12); // Demosaiced as RGB 32bit float data

    // Convert 14bit packed to data to 32bit RAW float data, not demosaiced
    float* raw = (float*)malloc(elements*sizeof(float));
    float** rrows = (float**)malloc(height*sizeof(float*));
    int rr = 0;
    for (;rr<height;rr++) {
        rrows[rr] = raw + rr*width;
    }

    int i = 0;
    int sparebits = 0;
    unsigned int acc = 0;
    unsigned int out = 0;
    short unsigned int* read = (short unsigned int*)input;
    float* write = raw;
    //printf("Decoding frame\n");

    int min = 70000;
    int max = 0;
    float imaxf=0.0f;
    float iminf=999999999.0f;
    while (i<elements) {
        short unsigned int r = *read++;
        if (byteSwap) 
            r = (r&0xFF00)>>8 | ((r&0x00FF)<<8);
        out = r;
        if (out==0) { // Dead pixel masking
            *write++ = *(write-2);
        } else {
            int ival = out-black;
            // To avoid artifacts from demosaicing at low levels
            ival += 15.0;
            if (ival<15) ival=15; // Don't want log2(0)

            float val = (float)ival;//64.0*log2((float)ival);
            *write++ = val;
        }
        i++;
    }

    // Now demosaic with CPU
    float* red = malloc(elements*sizeof(float));
    float** redrows = (float**)malloc(height*sizeof(float*));
    for (rr=0;rr<height;rr++) {
        redrows[rr] = red + rr*width;
    }
    float* green = malloc(elements*sizeof(float));
    float** greenrows = (float**)malloc(height*sizeof(float*));
    for (rr=0;rr<height;rr++) {
        greenrows[rr] = green + rr*width;
    }
    float* blue = malloc(elements*sizeof(float));
    float** bluerows = (float**)malloc(height*sizeof(float*));
    for (rr=0;rr<height;rr++) {
        bluerows[rr] = blue + rr*width;
    }

    demosaic(rrows,redrows,greenrows,bluerows,0,0,width,height);

    // Now interleave into final RGB float array
    float* outptr = (float*)PyByteArray_AS_STRING(ba);
    float* rptr = red;
    float* gptr = green;
    float* bptr = blue;
    float maxf=0.0f;
    float minf=999999999.0f;
    for (rr=0;rr<elements;rr++) {
           *outptr++ = (*rptr++);
           *outptr++ = (*gptr++);
           *outptr++ = (*bptr++);
    /*       float t = (*rptr++)/64.0;//exp2((*rptr++)/2048.0f);
           if (t<1.0f) t = 1.0f;
           float l = exp2(t)-15.0f; // Invert earlier offset
           if (l<0.0f) l = 0.0f;
           *outptr++ = l;

           t = (*gptr++)/64.0;//exp2((*gptr++)/2048.0f);
           if (t<1.0f) t = 1.0f;
           l = exp2(t)-15.0f;
           if (l<0.0f) l = 0.0f;
           *outptr++ = l;

           t = (*bptr++)/64.0;//exp2((*bptr++)/2048.0f);
           if (t<1.0f) t = 1.0f;
           l = exp2(t)-15.0f;
           if (l<0.0f) l = 0.0f;
           *outptr++ = l;*/
    }
    //printf("min=%d,max=%d,iminf=%f,imaxf=%f,minf=%f, maxf=%f\n",min,max,iminf,imaxf,minf,maxf);
    free(raw);
    free(rrows);
    free(red);
    free(redrows);
    free(green);
    free(greenrows);
    free(blue);
    free(bluerows);

    return ba;
}

static PyObject*
bitunpack_unpack14to16(PyObject* self, PyObject *args)
{
    unsigned const char* input = 0;
    int length = 0;
    int byteSwap = 0;
    if (!PyArg_ParseTuple(args, "t#i", &input, &length, &byteSwap))
        return NULL;
    PyObject* ba = PyByteArray_FromStringAndSize("",0);
    int elements = length*8/14;
    PyByteArray_Resize(ba,elements*2);
    unsigned char* baptr = (unsigned char*)PyByteArray_AS_STRING(ba);
    int i = 0;
    int sparebits = 0;
    unsigned int acc = 0;
    unsigned int out = 0;
    short unsigned int* read = (short unsigned int*)input;
    short unsigned int* write = (short unsigned int*)baptr;
    //printf("Decoding frame\n");

    Py_BEGIN_ALLOW_THREADS;
    while (i<elements) {
        if (sparebits<14) {
            short unsigned int r = *read++;
            if (byteSwap) 
                r = (r&0xFF00)>>8 | ((r&0x00FF)<<8);
            acc |= r;
            sparebits += 2;
            out = (acc>>sparebits)&0x3FFF;
        } else {
            sparebits += 2;
            out = (acc>>sparebits)&0x3FFF;
            sparebits = 0;
            acc = 0;
        }
        if (out==0) out = *(write-2); // Dead pixel masking
        *write++ = out;
        acc = (acc&((1<<sparebits)-1))<<16;
        i++;
    }
    Py_END_ALLOW_THREADS;
    PyObject *stat = Py_BuildValue("II",0,0);
    PyObject *rslt = PyTuple_New(2);
    PyTuple_SetItem(rslt, 0, ba);
    PyTuple_SetItem(rslt, 1, stat);
    return rslt;
}

static PyMethodDef methods[] = {
    { "unpack14to16", bitunpack_unpack14to16, METH_VARARGS, "Unpack a string of 14bit values to 16bit values" },
    { "demosaic14", bitunpack_demosaic14, METH_VARARGS, "Demosaic a 14bit RAW image into RGB float" },
    { "demosaic16", bitunpack_demosaic16, METH_VARARGS, "Demosaic a 16bit RAW image into RGB float" },
    { NULL, NULL, 0, NULL }
};

PyMODINIT_FUNC
initbitunpack(void)
{
    PyObject* m;

    m = Py_InitModule("bitunpack", methods);
    if (m == NULL)
        return;
    PyModule_AddStringConstant(m,"__version__","1.6");
}

