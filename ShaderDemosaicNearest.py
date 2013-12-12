"""
ShaderDemosaic.py
(c) Andrew Baldwin 2013

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

This is a very simple "nearest" shader which just returns
an image at half the bayer resolution
"""

import ShaderDemosaic

class ShaderDemosaicNearest(ShaderDemosaic.ShaderDemosaic): 
    demosaic_type = "Nearest"
    vertex_src = """
attribute vec4 vertex;
varying vec2 texcoord;
uniform float time;
uniform vec3 colourBalance;
uniform vec4 rawres;
void main() {
    gl_Position = vertex;
    texcoord = (vec2(.5*vertex.x+.5,.5-.5*vertex.y));
}
"""
    fragment_src = """
varying vec2 texcoord;
uniform float time;
uniform float black;
uniform vec3 colourBalance;
uniform vec4 rawres;
uniform sampler2D rawtex;

float red(vec2 coord) {
    // Return nearest red
    vec2 gridpos = coord*rawres.xy*0.5;
    vec2 set = floor(gridpos)*2.0;
    vec2 offset = fract(gridpos)*2.0;
    float sample = texture2D(rawtex,(set-vec2(0.,0.))*rawres.zw).r-black;
    return sample;
}
float green(vec2 coord) {
    vec2 gridpos = coord*rawres.xy*0.5;
    vec2 set = floor(gridpos)*2.0;
    vec2 offset = fract(gridpos)*2.0;
    
    float sample1 = log2(texture2D(rawtex,(set+vec2(1.0,0.0))*rawres.zw).r-black);
    float sample2 = log2(texture2D(rawtex,(set+vec2(0.0,1.0))*rawres.zw).r-black);
    return exp2(0.5*(sample1+sample2));
}
float blue(vec2 coord) {
    vec2 gridpos = coord*rawres.xy*0.5;
    vec2 set = floor(gridpos)*2.0;
    vec2 offset = fract(gridpos)*2.0;
    float sample = texture2D(rawtex,(set+vec2(1.0,1.0))*rawres.zw).r-black;
    return sample;
}

vec3 getColor(vec2 coord) {
    return vec3(red(coord),green(coord),blue(coord));    
}

void main() {
    gl_FragColor = vec4(getColor(texcoord),1.0);
}
"""


