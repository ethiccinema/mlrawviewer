"""
ShaderDemosaicCPU.py
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
uniform float tonemap;
uniform vec2 black;
uniform vec3 colourBalance;
uniform vec4 rawres;
uniform sampler2D rawtex;

void main() {
    vec3 colour = texture2D(rawtex,texcoord).rgb;
    // Simple highlight recovery
    vec3 ocol = colour;
    colour *= colourBalance;
    if (ocol.g > (black.y-black.x)){
        colour.g = 0.5*(colour.r+colour.b);
    }
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


