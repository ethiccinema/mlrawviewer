/*
bayz.h
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

enum {
    BAYZ_ERROR_BAD_SIGNATURE = -1,
    BAYZ_ERROR_NO_MEMORY = -2,
};

/* 
Take 14bit packed in 16bit LE words as input
Ouput compressed stream including header
*/
int bayz_encode14(int width, int height, unsigned short* bay14, void** bayz);
/* 
Convert packed 14bit bayer data to unpacked 16bit
*/
unsigned short* bayz_convert14to16(int width, int height, unsigned short* bay14);
/* 
Take 14bit values unpacked into 16bit LE words as input
Ouput compressed stream including header
*/
int bayz_encode16(int width, int height, unsigned short* bay16, void** bayz);
/* 
Take compressed stream as input
Return 14bit values in unpacked 16bit LE words
*/
int bayz_decode16(void* bayz, int* width, int* height, unsigned short** bay16);


