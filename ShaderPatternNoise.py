"""
ShaderPatternNoise.py
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

This shader adaptively averages rows or columns to identify sensor amplifier stripe noise
"""

import GLCompute
from OpenGL.GL import *
import numpy as np

class ShaderPatternNoise(GLCompute.Shader):
    vertex_src = """
attribute vec4 vertex;
varying vec2 texcoord;
uniform vec4 rawres;
void main() {
    gl_Position = vertex;
    texcoord = (vec2(.5*vertex.x+.5,.5+.5*vertex.y));
}
"""
    fragment_src = """
varying vec2 texcoord;
uniform vec4 rawres;
uniform float orientation;
uniform sampler2D rawtex;
uniform vec2 blackwhite;

void main() {
    float coll = 0.0;
    float colh = 0.0;
    float countl = 0.0;
    float counth = 0.0;
    if (orientation==1.0) {
        // Vertical
        float up4 = -4.0 * rawres.w;
        float up2 = -2.0 * rawres.w;
        float down2 = 2.0 * rawres.w;
        float down4 = 4.0 * rawres.w;
        if (texcoord.y<rawres.w*4.0) {
            up4 = down4;
            up2 = down2;
        }
        if (texcoord.y>(1.0-rawres.w*4.0)) {
            down4 = up4;
            down2 = up2;
        }
        float x=rawres.z*0.5;
        int maxi = int(rawres.x);
        for (int i=0;i<maxi;i++) {
            float up1 = texture2D(rawtex,texcoord+vec2(x,up4)).r;
            float up = texture2D(rawtex,texcoord+vec2(x,up2)).r;
            float mid = texture2D(rawtex,texcoord+vec2(x,0.0)).r;
            float down = texture2D(rawtex,texcoord+vec2(x,down2)).r;
            float down1 = texture2D(rawtex,texcoord+vec2(x,down4)).r;
            float lh = min(up,up1);
            float ll = max(up,up1);
            float rh = min(down,down1);
            float rl = max(down,down1);
            float hlo = max(lh,rh);
            float lhi = min(ll,rl);
            float med = mix(lhi,hlo,0.5); // Take mid point of mid samples
            float mul = mid/med;
            float mulz = abs(mul-1.0);
            float incr = step(mulz,0.01);   
            float loh = step((mid-blackwhite.x),(64.0/65536.0));
            float nloh = 1.0 - loh;
            coll += loh * incr * mul;
            countl += loh * incr;
            colh += nloh * incr * mul;
            counth += nloh * incr;
            x=x+rawres.z;
        }
        if (countl<5.0) coll = 1.0;
        else coll = coll/countl;
        if (counth<5.0) colh = 1.0;
        else colh = colh/counth;
    }
    else {
        // Horizontal
        float left4 = -4.0 * rawres.z;
        float left2 = -2.0 * rawres.z;
        float right2 = 2.0 * rawres.z;
        float right4 = 4.0 * rawres.z;
        if (texcoord.x<rawres.z*4.0) {
            left4 = right4;
            left2 = right2;
        }
        if (texcoord.x>(1.0-rawres.z*4.0)) {
            right4 = left4;
            right2 = left2;
        }
        float y=rawres.w*0.5;
        int maxi = int(rawres.y);
        for (int i=0;i<maxi;i++) {
            float lleft = texture2D(rawtex,texcoord+vec2(left4,y)).r;
            float left = texture2D(rawtex,texcoord+vec2(left2,y)).r;
            float mid = texture2D(rawtex,texcoord+vec2(0.0,y)).r;
            float right = texture2D(rawtex,texcoord+vec2(right2,y)).r;
            float rright = texture2D(rawtex,texcoord+vec2(right4,y)).r;
            float lh = min(lleft,left);
            float ll = max(lleft,left);
            float rh = min(rright,right);
            float rl = max(rright,right);
            float hlo = max(lh,rh);
            float lhi = min(ll,rl);
            float med = mix(lhi,hlo,0.5); // Take mid point of mid samples
            float mul = mid/med;
            float mulz = abs(mul-1.0);
            float incr = step(mulz,0.01);   
            float loh = step((mid-blackwhite.x),(64.0/65536.0));
            float nloh = 1.0-loh;
            coll += loh * incr * mul;
            countl += loh * incr;
            colh += nloh * incr * mul;
            counth += nloh * incr;
            y=y+rawres.w;
        }
        if (countl<10.0) coll = 1.0;
        else coll = coll/countl;
        if (counth<10.0) colh = 1.0;
        else colh = colh/counth;
    }
    gl_FragColor = vec4(coll,colh,0.0,0.0);
}
"""

    def __init__(self,**kwds):
        myclass = self.__class__
        super(ShaderPatternNoise,self).__init__(myclass.vertex_src,myclass.fragment_src,["rawtex","rawres","orientation","blackwhite"],**kwds)
        self.svbo = None
    def prepare(self,svbo):
        if self.svbo==None:
            self.svbo = svbo
            self.svbobase = svbo.allocate(4*12) 
            vertices = np.array((-1,-1,0,1,-1,0,-1,1,0,1,1,0),dtype=np.float32)
            self.svbo.update(vertices,self.svbobase)

    def draw(self,width,height,texture,orientation,black,white):
        self.use()
        self.blend(False)
        glVertexAttribPointer(self.vertex,3,GL_FLOAT,GL_FALSE,0,self.svbo.vboOffset(self.svbobase))
        glEnableVertexAttribArray(self.vertex)
        texture.bindtex(False)
        glUniform1i(self.uniforms["rawtex"], 0)
        glUniform1f(self.uniforms["orientation"], orientation)
        glUniform2f(self.uniforms["blackwhite"], black,white)
        w = width
        h = height
        if w>0 and h>0:
            glUniform4f(self.uniforms["rawres"], w, h, 1.0/float(w),1.0/float(h))
        glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)

    def calcStripescaleH(self,w,h):
        horiz = glReadPixels(0,0,w,1,GL_RGB,GL_FLOAT)
        lowrg = horiz[::2,0,0]
        highrg = horiz[::2,0,1]
        lowgb = horiz[1::2,0,0]
        highgb = horiz[1::2,0,1]
        horlrg = lowrg.mean()
        horhrg = highrg.mean()
        horlgb = lowgb.mean()
        horhgb = highgb.mean()
        print horlrg,horhrg,horlgb,horhgb
        return (horlrg,horhrg,horlgb,horhgb)
    
    def calcStripescaleV(self,w,h):
        vert = glReadPixels(0,0,1,h,GL_RGB,GL_FLOAT)
        lowrg = vert[0,::2,0]
        highrg = vert[0,::2,1]
        lowgb = vert[0,1::2,0]
        highgb = vert[0,1::2,1]
        verlrg = lowrg.mean()
        verhrg = highrg.mean()
        verlgb = lowgb.mean()
        verhgb = highgb.mean()
        return (verlrg,verhrg,verlgb,verhgb)

    

