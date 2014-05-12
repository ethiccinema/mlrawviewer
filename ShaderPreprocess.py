"""
ShaderPreprocess.py
(c) Andrew Baldwin 2014

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

This shader operates on the raw data prior to demosaicing pass
It has access to a previously rendered frame from the same sensor (may not be adjacent frame)
It also has offsets for horizontal and vertical stripe patterns already estimated
Output is 4 16bit values, the first of which should be an improved raw sample
The other 3 values should be updated sensor noise profile metadata based on previous versions of the same metadata

"""

import GLCompute
from OpenGL.GL import *
import numpy as np

class ShaderPreprocess(GLCompute.Shader):
    vertex_src = """
attribute vec4 vertex;
varying vec2 texcoord;
uniform vec4 rawres;
void main() {
    gl_Position = vertex;
    texcoord = (vec2(.5*vertex.x+.5,.5+.5*(vertex.y)));
}
"""
    fragment_src = """
varying vec2 texcoord;
uniform vec4 rawres;
uniform sampler2D lastex;
uniform sampler2D rawtex;
uniform sampler2D hortex;
uniform sampler2D vertex;
uniform vec4 stripescale;
uniform vec2 blackwhite;
uniform vec4 colourBalance;

void main() {
    // Calculate median and range of same-colour neighbours
    vec2 pixel = texcoord.xy*rawres.xy;
    vec2 pixelgrid = floor(mod(pixel,2.0));
    float rgb = pixelgrid.x+pixelgrid.y*2.0; 
    // 0=red (green l/r/u/d)
    // 1=green1 (red l/r, blue u/d)
    // 2=green2 (blue l/r, red u/d)
    // 3=blue (green l/r/u/d)
    float thisbalance = colourBalance.r;
    float upbalance = colourBalance.g;
    float leftbalance = colourBalance.g;
    if (rgb==1.0) {
        thisbalance = colourBalance.g;
        upbalance = colourBalance.b; 
        leftbalance = colourBalance.r; 
    } else if (rgb==2.0) {
        thisbalance = colourBalance.g;
        upbalance = colourBalance.r; 
        leftbalance = colourBalance.b; 
    } else if (rgb==3.0) {
        thisbalance = colourBalance.b;
        upbalance = colourBalance.g; 
        leftbalance = colourBalance.g; 
    } 
    float rawup = texture2D(rawtex,texcoord+vec2(0.0,-rawres.w*2.0)).r-blackwhite.r;
    float rawdown = texture2D(rawtex,texcoord+vec2(0.0,rawres.w*2.0)).r-blackwhite.r;
    float rawleft = texture2D(rawtex,texcoord+vec2(-rawres.z*2.0,0.0)).r-blackwhite.r;
    float rawright = texture2D(rawtex,texcoord+vec2(rawres.z*2.0,0.0)).r-blackwhite.r;
    float lh = min(rawup,rawdown);
    float ll = max(rawup,rawdown);
    float rh = min(rawleft,rawright);
    float rl = max(rawleft,rawright);
    float hlo = max(lh,rh);
    float lhi = min(ll,rl);
    float mednei = mix(lhi,hlo,0.5); // Take mid point of mid samples

    // Accumulate correlation of pixel with neighbours
    float raw = texture2D(rawtex,texcoord).r;
    // Apply stripe correction
    vec3 hor = texture2D(hortex,texcoord).rgb;
    vec3 ver = texture2D(vertex,texcoord).rgb;
    float mulh = mix(hor.r/stripescale.x,hor.g/stripescale.y,step(blackwhite.r+64.0/65536.0,raw));
    float mulv = mix(ver.r/stripescale.z,ver.g/stripescale.w,step(blackwhite.r+64.0/65536.0,raw));
    float mulp = mix(1.0,1.0/(mulh*mulv),step(blackwhite.r+0.0/65536.0,raw)*step(raw,blackwhite.g));
    raw = raw*mulp - blackwhite.r*(stripescale.x*stripescale.z - 1.0);
    float rawped = raw-blackwhite.r;
    float maxnei = max(max(ll,rl),rawped);
    float minnei = min(min(lh,rh),rawped);
    
    vec4 last = texture2D(lastex,texcoord);
    float correlation = last.g;
   
    float thiscor = step(0.0,rawped - maxnei); // Higher
    thiscor += step(0.0,minnei - rawped); // Lower
    correlation += step(abs(correlation),0.5)*(-0.02*step(0.5,thiscor)+0.01); // -0.01 for outside, +0.01 for inside if abs(correlation)<0.5 

    float detail = step(abs(rawped-rawup)+abs(rawped-rawdown)+abs(rawped-rawleft)+abs(rawped-rawright),0.1);
    float hide = step(correlation,-0.15); // If correlation less than -0.15, hide the pixel
    float notDetail = step(maxnei-minnei,max(0.0001,mednei*0.9));//,max(0.00001,mednei*0.001));
    float close = detail*step(abs(mednei-rawped),max(0.001,rawped*.0001))*0.5+hide;
    float closeold = detail*step(abs(last.b-blackwhite.r-rawped),max(0.0005,rawped*.0001))*step(rawped,0.01);
    raw = mix(raw,mednei+blackwhite.r,min(close,1.0));
    raw = mix(raw,last.b,0.5*closeold);
    raw = max(raw,blackwhite.r);


    // Highlight recovery and predemosaicing colour balance
    float rawup1 = (texture2D(rawtex,texcoord+vec2(0.0,-rawres.w)).r-blackwhite.r);
    float rawdown1 = (texture2D(rawtex,texcoord+vec2(0.0,rawres.w)).r-blackwhite.r);
    float rawleft1 = (texture2D(rawtex,texcoord+vec2(-rawres.z,0.0)).r-blackwhite.r);
    float rawright1 = (texture2D(rawtex,texcoord+vec2(rawres.z,0.0)).r-blackwhite.r);
    rawped = (raw-blackwhite.r);

    float white = blackwhite.g-blackwhite.r;
    float underwhite = step(rawped,white);
    // If this channel is overexposed, try to recover from u/d/l/r neighbours
    float udav = (rawup1+rawdown1)*0.5;
    float lrav = (rawleft1+rawright1)*0.5;
    float udavow = step(udav,white);
    float lravow = step(lrav,white);
    float over = (1.0-udavow)*(1.0-lravow);
    float recovered = (udav*udavow*upbalance+lrav*lravow*leftbalance+white*over)/(udavow+lravow+over);
    rawped = mix(recovered,rawped*thisbalance,underwhite);

    vec3 passon = vec3(correlation,raw,last.a);
    //gl_FragColor = vec4(min(1.0,notDetail),passon);
    gl_FragColor = vec4(blackwhite.r+rawped,passon);
}
"""

    def __init__(self,**kwds):
        myclass = self.__class__
        super(ShaderPreprocess,self).__init__(myclass.vertex_src,myclass.fragment_src,["rawtex","lastex","rawres","hortex","vertex","stripescale","blackwhite","colourBalance"],**kwds)
        self.svbo = None
    def prepare(self,svbo):
        if self.svbo==None:
            self.svbo = svbo
            self.svbobase = svbo.allocate(4*12) 
            vertices = np.array((-1,-1,0,1,-1,0,-1,1,0,1,1,0),dtype=np.float32)
            self.svbo.update(vertices,self.svbobase)

    def draw(self,width,height,rawtex,lastex,hortex,vertex,hl,hh,vl,vh,black,white,balance):
        self.use()
        self.blend(False)
        glVertexAttribPointer(self.vertex,3,GL_FLOAT,GL_FALSE,0,self.svbo.vboOffset(self.svbobase))
        glEnableVertexAttribArray(self.vertex)
        rawtex.bindtex(False) 
        lastex.bindtex(False,texnum=1)
        hortex.bindtex(False,texnum=2)
        vertex.bindtex(False,texnum=3)
        glUniform1i(self.uniforms["rawtex"], 0)
        glUniform1i(self.uniforms["lastex"], 1)
        glUniform1i(self.uniforms["hortex"], 2)
        glUniform1i(self.uniforms["vertex"], 3)
        glUniform4f(self.uniforms["stripescale"], hl,hh,vl,vh)
        glUniform4f(self.uniforms["colourBalance"], balance[0],balance[1],balance[2],balance[3])
        glUniform2f(self.uniforms["blackwhite"], black,white)
        w = width
        h = height
        if w>0 and h>0:
            glUniform4f(self.uniforms["rawres"], w, h, 1.0/float(w),1.0/float(h))
        glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)
