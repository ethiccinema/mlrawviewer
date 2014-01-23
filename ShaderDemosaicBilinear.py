"""
ShaderDemosaicBilinear.py
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

This is a reasonable bayer->RGB shader
which does interpolation in R, G and B.
R & B is normal bilinear interpolation
G is at 45 degreee rotation
"""

import ShaderDemosaic

class ShaderDemosaicBilinear(ShaderDemosaic.ShaderDemosaic):
    demosaic_type = "Bilinear"
    vertex_src = """
attribute vec4 vertex;
varying vec2 texcoord;
uniform vec3 colourBalance;
uniform float time;
uniform vec4 rawres;
void main() {
    gl_Position = vertex;
    texcoord = (vec2(.5*vertex.x+.5,.5-.5*vertex.y));
}
"""
    fragment_src = """
varying vec2 texcoord;
uniform vec3 colourBalance;
uniform float time;
uniform float tonemap;
uniform vec2 black;
uniform vec4 rawres;
uniform sampler2D rawtex;

float get(vec2 bayerpixel) {
    // Ensure we only sample within texture and from same colour as requested
    // Means edges don't get funny colours
    vec2 clampedpixel = clamp(bayerpixel,vec2(0.0),rawres.xy-1.0);
    vec2 diff = bayerpixel - clampedpixel;
    vec2 clampedcoord = (bayerpixel-diff*2.0)*rawres.zw;
    float raw = texture2D(rawtex,clampedcoord).r-black.x;
    return log2(clamp(raw,0.00001,1.0));
}

float red(vec2 coord) {
    // Return bilinear filtered red
    vec2 gridpos = coord*rawres.xy*0.5-0.25; // 0.25 = Top left corner of a 2x2 bayer block
    vec2 set = floor(gridpos)*2.0;
    vec2 offset = fract(gridpos);
    float tl = get(set);
    float tr = get(set+vec2(2.0,0.0));
    float bl = get(set+vec2(0.0,2.0));
    float br = get(set+vec2(2.0,2.0));
    float sample = exp2(mix(mix(tl,tr,offset.x),mix(bl,br,offset.x),offset.y));
    return sample;
}
float green(vec2 coord) {
    // Return bilinear filtered green
    vec2 gridpos = coord*rawres.xy*0.5-vec2(0.25);
    vec2 offset = fract(gridpos);
    vec2 set = floor(gridpos)*2.0;
    vec2 frommid = abs(offset - vec2(0.5));
    float shift = step(0.5,frommid.x + frommid.y);
    vec2 mid = step(0.5,offset)*2.0-1.0;
    set += shift*mid;
    offset = fract(offset+shift*mid*0.5);
    vec2 ic = vec2(offset.x + offset.y - 0.5, offset.y - offset.x + 0.5); // Rotate coordinates for mixing by 45 degrees
    float tl = get(set+vec2(1.0,0.0));
    float tr = get(set+vec2(2.0,1.0));
    float bl = get(set+vec2(0.0,1.0));
    float br = get(set+vec2(1.0,2.0));
    float sample = exp2(mix(mix(tl,tr,ic.x),mix(bl,br,ic.x),ic.y));
    return sample;
}
float blue(vec2 coord) {
    // Return bilinear filtered blue
    vec2 gridpos = coord*rawres.xy*0.5-0.75;
    vec2 set = floor(gridpos)*2.0;
    vec2 offset = fract(gridpos);
    float tl = get(set+vec2(1.0,1.0));
    float tr = get(set+vec2(3.0,1.0));
    float bl = get(set+vec2(1.0,3.0));
    float br = get(set+vec2(3.0,3.0));
    float sample = exp2(mix(mix(tl,tr,offset.x),mix(bl,br,offset.x),offset.y));
    return sample;
}

vec3 getColour(vec2 coord) {
    return vec3(red(coord),green(coord),blue(coord));
}

void main() {
    vec3 colour = getColour(texcoord);
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

