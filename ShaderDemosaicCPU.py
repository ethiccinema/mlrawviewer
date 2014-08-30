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
uniform sampler3D lut3d;
uniform sampler1D lut1d1;
uniform sampler1D lut1d2;
uniform mat3 colourMatrix;
uniform vec4 lutcontrol;

vec3 sRGBgamma(vec3 linear) {
    return mix(12.92*linear,(1.0+0.055)*pow(linear,vec3(1.0/2.4))-0.055,step(vec3(0.0031308),linear));
}

vec3 r709gamma(vec3 linear) {
    return mix(4.5*linear,(1.0+0.099)*pow(linear,vec3(0.45))-0.099,step(vec3(0.018),linear));
}

vec3 SLoggamma(vec3 linear) {
    //379.044*LOG(x/5088 + 0.037584, 10) + 630
    return (379.0 * (log2(linear * 16384.0 / 5088.0 + 0.037584)/log2(10.0)) + 630.0) / 1024.0 ;
}

vec3 SLog2gamma(vec3 linear) {
    //379.044*LOG(x/7200 + 0.037584, 10) + 630
    return (379.0 * (log2(linear * 16384.0 / 7200.0 + 0.037584)/log2(10.0)) + 630.0) / 1024.0 ;
}

vec3 LogCgamma(vec3 linear) {
    //IF(x < 88, 1.25*x, 272.LOG(x/950, 10) + 391)
    return mix(20480.0*linear,
        272.0 * (log2(linear * 16384.0 / 950.0)/log2(10.0)) + 391.0,
        step(vec3(88.0/16384.0),linear)) / 1024.0 ;
}

/* Native trilinear interpolation cannot be trusted not to
introduce quantising. Instead we must sample 8 nearest points
and mix explicitly.
*/
vec3 lut3drgb(vec3 crgb) {
    float lutn = lutcontrol.x;
    vec3 crd = crgb*(lutn-1.0);
    vec3 base = floor(crd);
    vec4 next = vec4(vec3(1.0/lutn),0.0);
    vec3 off = fract(crd);
    vec3 tl = vec3(0.5/lutn);
    base = base*next.rgb+tl;
    vec3 s000 = texture3D(lut3d,base).rgb;
    vec3 s001 = texture3D(lut3d,base+next.xww).rgb;
    vec3 s00 = mix(s000,s001,off.x);
    vec3 s010 = texture3D(lut3d,base+next.wyw).rgb;
    vec3 s011 = texture3D(lut3d,base+next.xyw).rgb;
    vec3 s01 = mix(s010,s011,off.x);
    vec3 s100 = texture3D(lut3d,base+next.wwz).rgb;
    vec3 s0 = mix(s00,s01,off.y);
    vec3 s101 = texture3D(lut3d,base+next.xwz).rgb;
    vec3 s10 = mix(s100,s101,off.x);
    vec3 s110 = texture3D(lut3d,base+next.wyz).rgb;
    vec3 s111 = texture3D(lut3d,base+next.xyz).rgb;
    vec3 s11 = mix(s110,s111,off.x);
    vec3 s1 = mix(s10,s11,off.y);
    vec3 result = mix(s0,s1,off.z);
    vec3 postlut = clamp(result,0.0,1.0);
    return postlut;
}
vec3 lut1drgb(sampler1D lut,float lutn,vec3 crgb) {
    vec3 crd = crgb*(lutn-1.0);
    vec3 base = floor(crd);
    float next = 1.0/lutn;
    vec3 off = fract(crd);
    vec3 tl = vec3(0.5/lutn);
    base = base*next+tl;
    float r0 = texture1D(lut,base.r).r;
    float r1 = texture1D(lut,base.r+next).r;
    float r = mix(r0,r1,off.r);
    float g0 = texture1D(lut,base.g).g;
    float g1 = texture1D(lut,base.g+next).g;
    float g = mix(g0,g1,off.g);
    float b0 = texture1D(lut,base.b).b;
    float b1 = texture1D(lut,base.b+next).b;
    float b = mix(b0,b1,off.b);
    vec3 postlut = clamp(vec3(r,g,b),0.0,1.0);
    return postlut;
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
    } else if (tonemap==5.0) {
        toneMapped = SLoggamma(colour);
    } else if (tonemap==6.0) {
        toneMapped = SLog2gamma(colour);
    } else if (tonemap==7.0) {
        toneMapped = LogCgamma(colour);
    }
    vec3 crgb = mix(colour,toneMapped,step(0.5,tonemap));
    if (lutcontrol.y>0.0)
        crgb = lut1drgb(lut1d1,lutcontrol.y,crgb);
    if (lutcontrol.x>0.0)
        crgb = lut3drgb(crgb);
    if (lutcontrol.z>0.0)
        crgb = lut1drgb(lut1d2,lutcontrol.z,crgb);
    gl_FragColor = vec4(crgb,1.0);
}
"""


