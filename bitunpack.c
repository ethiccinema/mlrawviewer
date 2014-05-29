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
        if (out==0) { // Dead pixel masking
            float old = *(write-2);
            *write++ = old;
        } else {
            int ival = out-black;
            // To avoid artifacts from demosaicing at low levels
            ival += 15.0;
            if (ival<15) ival=15; // Don't want log2(0)

            float val = (float)ival;//64.0*log2((float)ival);
            *write++ = val;
        }
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
    for (rr=0;rr<elements;rr++) {
           *outptr++ = (*rptr++);
           *outptr++ = (*gptr++);
           *outptr++ = (*bptr++);
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
    unsigned int out = 0;
    short unsigned int* read = (short unsigned int*)input;
    float* write = raw;
    //printf("Decoding frame\n");

    while (i<elements) {
        short unsigned int r = *read++;
        if (byteSwap) 
            r = (r&0xFF00)>>8 | ((r&0x00FF)<<8);
        out = r;
        if (out==0) { // Dead pixel masking
            float old = *(write-2);
            *write++ = old;
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

    Py_BEGIN_ALLOW_THREADS;
    demosaic(rrows,redrows,greenrows,bluerows,0,0,width,height);
    Py_END_ALLOW_THREADS;

    // Now interleave into final RGB float array
    float* outptr = (float*)PyByteArray_AS_STRING(ba);
    float* rptr = red;
    float* gptr = green;
    float* bptr = blue;
    for (rr=0;rr<elements;rr++) {
           *outptr++ = (*rptr++);
           *outptr++ = (*gptr++);
           *outptr++ = (*bptr++);
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

typedef struct _demosaicer {
    int width;
    int height;
    float* raw;
    float** rrows;
    float* red;
    float** redrows;
    float* green;
    float** greenrows;
    float* blue;
    float** bluerows;
} demosaicer;

const char* DEMOSAICER_NAME = "demosaicer";
static void
bitunpack_freedemosaicer(PyObject* self)
{
    //printf("Free demosaicer called\n");
    demosaicer* dem = (demosaicer*)PyCapsule_GetPointer(self,DEMOSAICER_NAME);
    if (dem == NULL)
        return;
    //printf("Free demosaicer releasing buffer w:%d h:%d\n",dem->width,dem->height);
    free(dem->raw);
    free(dem->rrows);
    free(dem->red);
    free(dem->redrows);
    free(dem->green);
    free(dem->greenrows);
    free(dem->blue);
    free(dem->bluerows);
    free(dem);
}

static PyObject*
bitunpack_demosaicer(PyObject* self, PyObject *args)
{
    int width = 0;
    int height = 0;
    if (!PyArg_ParseTuple(args, "ii", &width, &height))
        return NULL;

    int elements = width*height;
    
    demosaicer* dem = (demosaicer*)calloc(1,sizeof(demosaicer));
    dem->width = width;
    dem->height = height; 
    dem->raw = (float*)malloc(elements*sizeof(float));
    dem->rrows = (float**)malloc(dem->height*sizeof(float*));
    int rr = 0;
    for (;rr<dem->height;rr++) {
        dem->rrows[rr] = dem->raw + rr*dem->width;
    }
    dem->red = malloc(elements*sizeof(float));
    dem->redrows = (float**)malloc(dem->height*sizeof(float*));
    for (rr=0;rr<dem->height;rr++) {
        dem->redrows[rr] = dem->red + rr*dem->width;
    }
    dem->green = malloc(elements*sizeof(float));
    dem->greenrows = (float**)malloc(dem->height*sizeof(float*));
    for (rr=0;rr<dem->height;rr++) {
        dem->greenrows[rr] = dem->green + rr*dem->width;
    }
    dem->blue = malloc(elements*sizeof(float));
    dem->bluerows = (float**)malloc(dem->height*sizeof(float*));
    for (rr=0;rr<dem->height;rr++) {
        dem->bluerows[rr] = dem->blue + rr*dem->width;
    }

    return PyCapsule_New(dem,DEMOSAICER_NAME,bitunpack_freedemosaicer);
}

static PyObject*
bitunpack_predemosaic14(PyObject* self, PyObject *args)
{
    unsigned const char* input = 0;
    int length = 0;
    int width = 0;
    int height = 0;
    int black = 2000;
    int byteSwap = 0;
    PyObject* demosaicerobj;
    if (!PyArg_ParseTuple(args, "Ot#iiii", &demosaicerobj, &input, &length, &width, &height, &black, &byteSwap))
        return NULL;
    demosaicer* dem = (demosaicer*)PyCapsule_GetPointer(demosaicerobj,DEMOSAICER_NAME);
    if (dem == NULL)
        return NULL;
    if (dem->width != width || dem->height != height)
        return NULL;

    int elements = width * height;
    int i = 0;
    int sparebits = 0;
    unsigned int acc = 0;
    unsigned int out = 0;
    short unsigned int* read = (short unsigned int*)input;
    float* write = dem->raw;

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
        if (out==0) { // Dead pixel masking
            float old = *(write-2);
            *write++ = old;
        } else {
            int ival = out-black;
            // To avoid artifacts from demosaicing at low levels
            ival += 15.0;
            if (ival<15) ival=15; // Don't want log2(0)

            float val = (float)ival;//64.0*log2((float)ival);
            *write++ = val;
        }
        acc = (acc&((1<<sparebits)-1))<<16;
        i++;
    }
    Py_END_ALLOW_THREADS;
    Py_RETURN_NONE;
}

static PyObject*
bitunpack_predemosaic16(PyObject* self, PyObject *args)
{
    unsigned const char* input = 0;
    int length = 0;
    int width = 0;
    int height = 0;
    int black = 2000;
    int byteSwap = 0;
    PyObject* demosaicerobj;
    if (!PyArg_ParseTuple(args, "Ot#iiii", &demosaicerobj, &input, &length, &width, &height, &black, &byteSwap))
        return NULL;
    demosaicer* dem = (demosaicer*)PyCapsule_GetPointer(demosaicerobj,DEMOSAICER_NAME);
    if (dem == NULL)
        return NULL;
    if (dem->width != width || dem->height != height)
        return NULL;

    int elements = width*height;
    int i = 0;
    unsigned int out = 0;
    short unsigned int* read = (short unsigned int*)input;
    float* write = dem->raw;
    //printf("Decoding frame\n");

    Py_BEGIN_ALLOW_THREADS;
    while (i<elements) {
        short unsigned int r = *read++;
        if (byteSwap) 
            r = (r&0xFF00)>>8 | ((r&0x00FF)<<8);
        out = r;
        if (out==0) { // Dead pixel masking
            float old = *(write-2);
            *write++ = old;
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
    Py_END_ALLOW_THREADS;
    Py_RETURN_NONE;
}

static PyObject*
bitunpack_demosaic(PyObject* self, PyObject *args)
{
    PyObject* demosaicerobj;
    int x;
    int y;
    int width;
    int height;
    if (!PyArg_ParseTuple(args, "Oiiii", &demosaicerobj, &x, &y, &width, &height))
        return NULL;
    demosaicer* dem = (demosaicer*)PyCapsule_GetPointer(demosaicerobj,DEMOSAICER_NAME);
    if (dem == NULL)
        return NULL;

    Py_BEGIN_ALLOW_THREADS;
    demosaic(dem->rrows,dem->redrows,dem->greenrows,dem->bluerows,x,y,width,height);
    Py_END_ALLOW_THREADS;
    Py_RETURN_NONE;
}

static PyObject*
bitunpack_postdemosaic(PyObject* self, PyObject *args)
{
    PyObject* demosaicerobj;
    if (!PyArg_ParseTuple(args, "O", &demosaicerobj))
        return NULL;
    demosaicer* dem = (demosaicer*)PyCapsule_GetPointer(demosaicerobj,DEMOSAICER_NAME);
    if (dem == NULL)
        return NULL;

    //printf("width %d height %d\n",width,height);
    PyObject* ba = PyByteArray_FromStringAndSize("",0);
    int elements = dem->width * dem->height;
    PyByteArray_Resize(ba,elements*12); // Demosaiced as RGB 32bit float data

    // Now interleave into final RGB float array
    float* outptr = (float*)PyByteArray_AS_STRING(ba);
    float* rptr = dem->red;
    float* gptr = dem->green;
    float* bptr = dem->blue;
    int rr;
    for (rr=0;rr<elements;rr++) {
           *outptr++ = (*rptr++);
           *outptr++ = (*gptr++);
           *outptr++ = (*bptr++);
    }
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
    { "demosaicer", bitunpack_demosaicer, METH_VARARGS, "Create a demosaicer object" },
    { "predemosaic14", bitunpack_predemosaic14, METH_VARARGS, "Prepare to demosaic a 14bit RAW image into RGB float" },
    { "predemosaic16", bitunpack_predemosaic16, METH_VARARGS, "Prepare to demosaic a 16bit RAW image into RGB float" },
    { "demosaic", bitunpack_demosaic, METH_VARARGS, "Do a unit of demosaicing work (can be from any thread." },
    { "postdemosaic", bitunpack_postdemosaic, METH_VARARGS, "Complete a demosaicing job. Returns the image." },

    { NULL, NULL, 0, NULL }
};

PyMODINIT_FUNC
initbitunpack(void)
{
    PyObject* m;

    m = Py_InitModule("bitunpack", methods);
    if (m == NULL)
        return;
    PyModule_AddStringConstant(m,"__version__","2.0");
}

