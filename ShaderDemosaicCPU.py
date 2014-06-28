"""
ShaderDemosaicCPU.py
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

Take the ouput of a CPU demosaic
and apply colourBalance and tone mapping
"""

import ShaderDemosaic

class ShaderDemosaicCPU(ShaderDemosaic.ShaderDemosaic): 
    demosaic_type = "CPU"
    size_minus_one = False
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

vec3 sRGBgamma(vec3 linear) {
    return mix(12.92*linear,(1.0+0.055)*pow(linear,vec3(1.0/2.4))-0.055,step(vec3(0.0031308),linear));
}

vec3 r709gamma(vec3 linear) {
    return mix(4.5*linear,(1.0+0.099)*pow(linear,vec3(0.45))-0.099,step(vec3(0.018),linear));
}

void main() {
    vec3 colour = texture2D(rawtex,texcoord).rgb;
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
        colour *= 6.0; // To make it perceptually similar level to sRGB gamma
        toneMapped = colour/(1.0 + colour);
    } else if (tonemap==2.0) {
        toneMapped = log2(1.0+1024.0*clamp(colour,0.0,1.0))/10.0;
    } else if (tonemap==3.0) {
        toneMapped = sRGBgamma(clamp(colour,0.0,1.0));
    } else if (tonemap==4.0) {
        toneMapped = r709gamma(clamp(colour,0.0,1.0));
    }
    colour = mix(colour,toneMapped,step(0.5,tonemap));
    gl_FragColor = vec4(colour,1.0);
}
"""


