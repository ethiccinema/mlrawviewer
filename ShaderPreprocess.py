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

void main() {
    float raw = texture2D(rawtex,texcoord).r;
    vec4 last = texture2D(lastex,texcoord).rgba;
    vec3 hor = texture2D(hortex,texcoord).rgb;
    vec3 ver = texture2D(vertex,texcoord).rgb;
    float mulh = mix(hor.r/stripescale.x,hor.g/stripescale.y,step(blackwhite.r+64.0/65536.0,raw));
    float mulv = mix(ver.r/stripescale.z,ver.g/stripescale.w,step(blackwhite.r+64.0/65536.0,raw));
    float pix = (raw/(mulh*mulv));
    vec3 passon = last.gba; // Do nothing
    gl_FragColor = vec4(pix,passon);
}
"""

    def __init__(self,**kwds):
        myclass = self.__class__
        super(ShaderPreprocess,self).__init__(myclass.vertex_src,myclass.fragment_src,["rawtex","lastex","rawres","hortex","vertex","stripescale","blackwhite"],**kwds)
        self.svbo = None
    def prepare(self,svbo):
        if self.svbo==None:
            self.svbo = svbo
            self.svbobase = svbo.allocate(4*12) 
            vertices = np.array((-1,-1,0,1,-1,0,-1,1,0,1,1,0),dtype=np.float32)
            self.svbo.update(vertices,self.svbobase)

    def draw(self,width,height,rawtex,lastex,hortex,vertex,hl,hh,vl,vh,black,white):
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
        glUniform2f(self.uniforms["blackwhite"], black,white)
        w = width
        h = height
        if w>0 and h>0:
            glUniform4f(self.uniforms["rawres"], w, h, 1.0/float(w),1.0/float(h))
        glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)
