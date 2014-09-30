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
    linear_lut = True
    size_minus_one = False
    vertex_src = """
attribute vec4 vertex;
varying vec2 texcoord;
uniform vec4 colourBalance;
uniform float time;
uniform vec4 rawres;
void main() {
    gl_Position = vertex;
    texcoord = (vec2(.5*vertex.x+.5,.5-.5*vertex.y));
}
"""
    fragment_src = """
varying vec2 texcoord;
uniform vec4 colourBalance;
uniform float time;
uniform float tonemap;
uniform vec4 black; //black,white,recover,cfa
uniform vec4 rawres;
uniform sampler2D rawtex;
uniform sampler3D lut3d;
uniform sampler1D lut1d1;
uniform sampler1D lut1d2;
uniform mat3 colourMatrix;
uniform vec4 lutcontrol;

vec3 getColour(vec2 coord) {
    vec2 pixcoord = step(0.5,fract((coord-rawres.zw*0.5)*rawres.xy*0.5+0.25));
    float pixel = pixcoord.y*2.0+pixcoord.x; // Bayer pixel number at coord
    float c = (max(0.000001,texture2D(rawtex,coord).r-black.x));
    float u = (max(0.000001,texture2D(rawtex,coord-vec2(0.0,rawres.w)).r-black.x));
    float d = (max(0.000001,texture2D(rawtex,coord+vec2(0.0,rawres.w)).r-black.x));
    float l = (max(0.000001,texture2D(rawtex,coord-vec2(rawres.z,0.0)).r-black.x));
    float r = (max(0.000001,texture2D(rawtex,coord+vec2(rawres.z,0.0)).r-black.x));
    float u2 = (max(0.000001,texture2D(rawtex,coord-vec2(0.0,2.*rawres.w)).r-black.x));
    float d2 = (max(0.000001,texture2D(rawtex,coord+vec2(0.0,2.*rawres.w)).r-black.x));
    float l2 = (max(0.000001,texture2D(rawtex,coord-vec2(2.*rawres.z,0.0)).r-black.x));
    float r2 = (max(0.000001,texture2D(rawtex,coord+vec2(2.*rawres.z,0.0)).r-black.x));
    float ul = (max(0.000001,texture2D(rawtex,coord-rawres.zw).r-black.x));
    float ur = (max(0.000001,texture2D(rawtex,coord+vec2(rawres.z,-rawres.w)).r-black.x));
    float dl = (max(0.000001,texture2D(rawtex,coord-vec2(rawres.z,-rawres.w)).r-black.x));
    float dr = (max(0.000001,texture2D(rawtex,coord+rawres.zw).r-black.x));
    float red,green,blue;
    if (black.w==1.0) { // GBRG, e.g. BMPCC
        if (pixel==0.0) {
            red=(d+u)*0.5;
            green=c;
            blue=(l+r)*0.5;
        } else if (pixel==1.0) {
            red=(dl+ul+ur+dr)*0.25;
            green=(u+d+l+r)*0.25;
            blue=c;
        } else if (pixel==2.0) {
            red=c;
            green=(u+d+l+r)*0.25;
            blue=(ul+dl+ur+dr)*0.25;
        } else if (pixel==3.0) {
            red=(l+r)*0.5;
            green=c;
            blue=(u+d)*0.5;
        }
    } else { // RGGB e.g. Canon
        if (pixel==2.0) {
            green=c;
            red=(d+u)*0.5;
            blue=(l+r)*0.5;
        } else if (pixel==3.0) {
            /*float gbu = u - (u2+c)*0.5;
            float gbd = d - (d2+c)*0.5;
            float gbl = l - (l2+c)*0.5;
            float gbr = r - (r2+c)*0.5;
            float hch = gbr - gbl;
            float hcv = gbd - gbu;
            float gb = mix(step(abs(hch),abs(hcv)),gbu+hcv*0.5,gbl+hch*0.5);
            green = c+gb; */
            green=(u+d+l+r)*0.25;
            red=(dl+ul+ur+dr)*0.25;
            blue=c;
        } else if (pixel==0.0) {
            /*float gru = u - (u2+c)*0.5;
            float grd = d - (d2+c)*0.5;
            float grl = l - (l2+c)*0.5;
            float grr = r - (r2+c)*0.5;
            float hch = grr - grl;
            float hcv = grd - gru;
            float gr = mix(step(abs(hch),abs(hcv)),gru+hcv*0.5,grl+hch*0.5);
            green= c+gr;*/
            green=(u+d+l+r)*0.25;
            red=c;
            blue=(ul+dl+ur+dr)*0.25;
        } else if (pixel==1.0) {
            red=(l+r)*0.5;
            green=c;
            blue=(u+d)*0.5;
        }
    }
    return (vec3(red,green,blue));
}

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
    //114*LOG(x/270 + 1, 2) + 90
    return (114.0 * log2(linear * 16384.0 / 270.0 + 1.0) + 90.0) / 1024.0 ;
}

vec3 LogCgamma(vec3 linear) {
    //IF(x < 88, 1.25*x, 272.LOG(x/950, 10) + 391)
    return mix(20480.0*linear,
        272.0 * (log2(linear * 16384.0 / 950.0)/log2(10.0)) + 391.0,
        step(vec3(88.0/16384.0),linear)) / 1024.0;
}

vec3 CLoggamma(vec3 linear) {
    //155*LOG(x/480 + 1, 2) + 96
    return (155.0 * log2(linear * 16384.0 / 480.0 + 1.0) + 96.0) / 1024.0 ;
}

/* Native trilinear interpolation cannot be trusted not to
introduce quantising. Instead we must sample 8 nearest points
and mix explicitly.
*/
vec3 lut3drgb(vec3 crgb) {
    float lutn = lutcontrol.x;
    vec3 crd = crgb*(lutn-1.0)*(1.0/lutn)+(0.5/lutn);
    vec3 result = texture3D(lut3d,crd).rgb;
    vec3 postlut = clamp(result,0.0,1.0);
    return postlut;
}
vec3 lut1drgb(sampler1D lut,float lutn,vec3 crgb) {
    vec3 crd = crgb*(lutn-1.0)*(1.0/lutn)+(0.5/lutn);
    float r = texture1D(lut,crd.r).r;
    float g = texture1D(lut,crd.g).g;
    float b = texture1D(lut,crd.b).b;
    vec3 postlut = clamp(vec3(r,g,b),0.0,1.0);
    return postlut;
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
        colour *= 6.0; // To make it perceptually similar level to sRGB gamma
        toneMapped = colour/(1.0 + colour);
    } else if (tonemap==2.0) {
        toneMapped = log2(1.0+256.0*colour)/8.0;
    } else if (tonemap==3.0) {
        toneMapped = sRGBgamma(colour);
    } else if (tonemap==4.0) {
        toneMapped = r709gamma(colour);
    } else if (tonemap==5.0) {
        toneMapped = SLoggamma(colour);
    } else if (tonemap==6.0) {
        toneMapped = SLog2gamma(colour);
    } else if (tonemap==7.0) {
        toneMapped = LogCgamma(colour);
    } else if (tonemap==8.0) {
        toneMapped = CLoggamma(colour);
    }
    vec3 crgb = mix(colour,clamp(toneMapped,0.0,1.0),step(0.5,tonemap));
    if (lutcontrol.y>0.0)
        crgb = lut1drgb(lut1d1,lutcontrol.y,crgb);
    if (lutcontrol.x>0.0)
        crgb = lut3drgb(crgb);
    if (lutcontrol.z>0.0)
        crgb = lut1drgb(lut1d2,lutcontrol.z,crgb);
    gl_FragColor = vec4(crgb,1.0);
}

"""

