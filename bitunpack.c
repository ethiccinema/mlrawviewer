#include <Python.h>

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
   
    unsigned int statmin = 1<<14-1;
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
    { NULL, NULL, 0, NULL }
};

PyMODINIT_FUNC
initbitunpack(void)
{
    PyObject* m;

    m = Py_InitModule("bitunpack", methods);
    if (m == NULL)
        return;
    PyModule_AddStringConstant(m,"__version__","1.1");
}

