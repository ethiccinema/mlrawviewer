"""
ShaderDemosaicNearest.py
(c) Andrew Baldwin 2013-2014

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
uniform vec4 colourBalance;
uniform vec4 rawres;
void main() {
    gl_Position = vertex;
    texcoord = (vec2(.5*vertex.x+.5,.5-.5*vertex.y));
}
"""
    fragment_src = """
varying vec2 texcoord;
uniform float time;
uniform float tonemap;
uniform vec4 black;
uniform vec4 colourBalance;
uniform vec4 rawres;
uniform sampler2D rawtex;
uniform mat3 colourMatrix;

float red(vec2 coord) {
    // Return nearest red
    vec2 gridpos = coord*rawres.xy*0.5;
    vec2 set = floor(gridpos)*2.0;
    vec2 offset = fract(gridpos)*2.0;
    float sample = texture2D(rawtex,(set-vec2(0.,0.))*rawres.zw).r-black.x;
    return sample;
}
float green(vec2 coord) {
    vec2 gridpos = coord*rawres.xy*0.5;
    vec2 set = floor(gridpos)*2.0;
    vec2 offset = fract(gridpos)*2.0;
    
    float sample1 = log2(texture2D(rawtex,(set+vec2(1.0,0.0))*rawres.zw).r-black.x);
    float sample2 = log2(texture2D(rawtex,(set+vec2(0.0,1.0))*rawres.zw).r-black.x);
    return exp2(0.5*(sample1+sample2));
}
float blue(vec2 coord) {
    vec2 gridpos = coord*rawres.xy*0.5;
    vec2 set = floor(gridpos)*2.0;
    vec2 offset = fract(gridpos)*2.0;
    float sample = texture2D(rawtex,(set+vec2(1.0,1.0))*rawres.zw).r-black.x;
    return sample;
}

vec3 getColour(vec2 coord) {
    return vec3(red(coord),green(coord),blue(coord));    
}

void main() {
    vec3 colour = getColour(texcoord);
    // Simple highlight recovery
    vec3 ocol = colour;
    colour *= colourBalance.rgb * colourBalance.a;
    colour = colourMatrix * colour;
    // Very simple highlight recovery if preprocessing not in use
    colour.g = mix(colour.g,0.5*(colour.r+colour.b),step(black.y-black.x,ocol.g)*black.b);
    float levelAdjust = 1.0/(black.y - black.x);
    colour *= levelAdjust;
    vec3 toneMapped = colour;
    if (tonemap==1.0) {
        toneMapped = colour/(1.0 + colour);
    } else {
        toneMapped = log2(1.0+1024.0*clamp(colour/16.0,0.0,1.0))/10.0;
    }
    colour = mix(colour,toneMapped,step(0.5,tonemap));
    gl_FragColor = vec4(colour,1.0);
}
"""


