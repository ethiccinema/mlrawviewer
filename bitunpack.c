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
    if (!PyArg_ParseTuple(args, "t#iii", &input, &length, &width, &height, &black))
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
    while (i<elements) {
        if (sparebits<14) {
            acc |= *read++;
            sparebits += 2;
            out = (acc>>sparebits)&0x3FFF;
        } else {
            sparebits += 2;
            out = (acc>>sparebits)&0x3FFF;
            sparebits = 0;
            acc = 0;
        }
        if (out<min) min=out;
        if (out>max) max=out;
        int ival = out-black;
        if (ival<1) ival=1;
        float val = 256.0*log2(1.0*(((float)(ival)))/65535.0f);
        *write++ = val;
        acc = (acc&((1<<sparebits)-1))<<16;
        i++;
    }

    printf("min=%d, max=%d\n",min,max);
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
    for (rr=0;rr<elements;rr++) {
           float t = *rptr++;
           *outptr++ = t;
           t = *gptr++;
           *outptr++ = t;
           t = *bptr++;
           *outptr++ = t;
    }
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
    if (!PyArg_ParseTuple(args, "t#", &input, &length))
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
   
    unsigned int statmin = (1<<14)-1;
    unsigned int statmax = 0;
 
    while (i<elements) {
        if (sparebits<14) {
            acc |= *read++;
            sparebits += 2;
            out = (acc>>sparebits)&0x3FFF;
        } else {
            sparebits += 2;
            out = (acc>>sparebits)&0x3FFF;
            sparebits = 0;
            acc = 0;
        }
        *write++ = out;
        if (out<statmin) statmin = out;
        if (out>statmax) statmax = out;
        acc = (acc&((1<<sparebits)-1))<<16;
        i++;
    }
    PyObject *stat = Py_BuildValue("II",statmin,statmax);
    PyObject *rslt = PyTuple_New(2);
    PyTuple_SetItem(rslt, 0, ba);
    PyTuple_SetItem(rslt, 1, stat);
    return rslt;
}

static PyMethodDef methods[] = {
    { "unpack14to16", bitunpack_unpack14to16, METH_VARARGS, "Unpack a string of 14bit values to 16bit values" },
    { "demosaic14", bitunpack_demosaic14, METH_VARARGS, "Demosaic a 14bit RAW image into RGB float" },
    { NULL, NULL, 0, NULL }
};

PyMODINIT_FUNC
initbitunpack(void)
{
    PyObject* m;

    m = Py_InitModule("bitunpack", methods);
    if (m == NULL)
        return;
    PyModule_AddStringConstant(m,"__version__","1.2");
}

