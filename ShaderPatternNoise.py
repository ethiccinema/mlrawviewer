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

void main() {
    float col = 0.0;
    if (orientation==1.0) {
        // Vertical
        float up4 = -4.0 * rawres.w;
        float up2 = -2.0 * rawres.w;
        float down2 = 2.0 * rawres.w;
        float down4 = 4.0 * rawres.w;
        float count = 0.0;
        float x=rawres.z*0.5;
        float up1 = texture2D(rawtex,texcoord+vec2(x,up4));
        float up = texture2D(rawtex,texcoord+vec2(x,up2));
        float mid = texture2D(rawtex,texcoord+vec2(x,0.0));
        float down = texture2D(rawtex,texcoord+vec2(x,down2));
        float down1 = texture2D(rawtex,texcoord+vec2(x,down4));
        for (int i=0;i<1200;i++) {
            if (i<rawres.y) {
                x=rawres.z*0.5+float(i)*rawres.z;
                up1 = 0.9 * up1 + 0.1 * texture2D(rawtex,texcoord+vec2(x,up4));
                up = 0.9 * up + 0.1 * texture2D(rawtex,texcoord+vec2(x,up2));
                float mid = texture2D(rawtex,texcoord+vec2(x,0.0));
                down = 0.9 * down + 0.1 * texture2D(rawtex,texcoord+vec2(x,down2));
                down1 = 0.9 * down1 + 0.1 * texture2D(rawtex,texcoord+vec2(x,down4));
                float av = abs(up-mid)+abs(up1-mid)+abs(down-mid)+abs(down1-mid);
                if ((av<(0.10/256.0))&&((mid-2000.0/65536.0)<(1.0/256.0))) {
                    col += (mid - 0.25*(up1+up+down+down1));
                    count += 1.0;
                }
            }
        }
        if (count<10.0) col = 0.0;
        else col = col/count;
    }
    else {
        // Horizontal
        float left4 = -4.0 * rawres.z;
        float left2 = -2.0 * rawres.z;
        float right2 = 2.0 * rawres.z;
        float right4 = 4.0 * rawres.z;
        float count = 0.0;
        float y=rawres.w*0.5;
        float lleft = texture2D(rawtex,texcoord+vec2(left4,y));
        float left = texture2D(rawtex,texcoord+vec2(left2,y));
        float right = texture2D(rawtex,texcoord+vec2(right2,y));
        float rright = texture2D(rawtex,texcoord+vec2(right4,y));
        for (int i=0;i<3000;i++) {
            if (i<rawres.x) {
                y=rawres.w*0.5 + float(i)*rawres.w;
                lleft = lleft*0.1 + 0.9*texture2D(rawtex,texcoord+vec2(left4,y));
                left = left*0.1 + 0.9*texture2D(rawtex,texcoord+vec2(left2,y));
                float mid = texture2D(rawtex,texcoord+vec2(0.0,y));
                right = right*0.1 + 0.9*texture2D(rawtex,texcoord+vec2(right2,y));
                rright = rright*0.1 + 0.9*texture2D(rawtex,texcoord+vec2(right4,y));
                float av = abs(left-mid)+abs(lleft-mid)+abs(right-mid)+abs(rright-mid);
                if ((av<(0.10/256.0))&&((mid-2000.0/65536.0)<(1.0/256.0))) {
                    col += (mid - 0.25*(lleft+left+right+rright));
                    count += 1.0;
                }
            }
        }
        if (count<10.0) col = 0.0;
        else col = col/count;
    }
    gl_FragColor = vec4(col);
}
"""

    def __init__(self,**kwds):
        myclass = self.__class__
        super(ShaderPatternNoise,self).__init__(myclass.vertex_src,myclass.fragment_src,["rawtex","rawres","orientation"],**kwds)
        self.svbo = None
    def prepare(self,svbo):
        if self.svbo==None:
            self.svbo = svbo
            self.svbobase = svbo.allocate(4*12) 
            vertices = np.array((-1,-1,0,1,-1,0,-1,1,0,1,1,0),dtype=np.float32)
            self.svbo.update(vertices,self.svbobase)

    def draw(self,width,height,texture,orientation):
        self.use()
        self.blend(False)
        glVertexAttribPointer(self.vertex,3,GL_FLOAT,GL_FALSE,0,self.svbo.vboOffset(self.svbobase))
        glEnableVertexAttribArray(self.vertex)
        texture.bindtex(False)
        glUniform1i(self.uniforms["rawtex"], 0)
        glUniform1f(self.uniforms["orientation"], orientation)
        w = width
        h = height
        if w>0 and h>0:
            glUniform4f(self.uniforms["rawres"], w, h, 1.0/float(w),1.0/float(h))
        glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)
         
    

