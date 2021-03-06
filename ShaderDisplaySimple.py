"""
ShaderDisplaySimple.py
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
"""

import GLCompute
from OpenGL.GL import *
import numpy as np

class ShaderDisplaySimple(GLCompute.Shader):
    vertex_src = """
attribute vec4 vertex;
varying vec2 texcoord;
uniform float time;
uniform vec4 rawres;
uniform vec4 activeArea; // Only display this area tl.x,tl.y,w,h in pixels
void main() {
    gl_Position = vertex;
    vec2 tl = activeArea.xy*rawres.zw;
    vec2 br = tl + activeArea.zw*rawres.zw;
    float temp = tl.y;
    tl.y = 1.0 - br.y;
    br.y = 1.0 - temp;
    //br.y = rawres.w-br.y;
    //tl.y = rawres.w-tl.y;
    texcoord = (vec2(.5*vertex.x+.5,.5+.5*vertex.y));
    texcoord = max(min(texcoord,br),tl);
}
"""
    fragment_src = """
varying vec2 texcoord;
uniform float time;
uniform vec4 rawres;
uniform sampler2D tex;

void main() {
    vec3 col = texture2D(tex,texcoord).rgb;
    gl_FragColor = vec4(col,1.);
}
"""

    def __init__(self,**kwds):
        myclass = self.__class__
        super(ShaderDisplaySimple,self).__init__(myclass.vertex_src,myclass.fragment_src,["time","tex","rawres","activeArea"],**kwds)
        self.svbo = None
    def prepare(self,svbo):
        if self.svbo==None:
            self.svbo = svbo
            self.svbobase = svbo.allocate(4*12)
            vertices = np.array((-1,-1,0,1,-1,0,-1,1,0,1,1,0),dtype=np.float32)
            self.svbo.update(vertices,self.svbobase)

    def draw(self,width,height,texture,activeArea=None):
        self.use()
        glVertexAttribPointer(self.vertex,3,GL_FLOAT,GL_FALSE,0,self.svbo.vboOffset(self.svbobase))
        glEnableVertexAttribArray(self.vertex)
        texture.bindtex(True) # Use linear filter
        glUniform1i(self.uniforms["tex"], 0)
        w = texture.width
        h = texture.height
        if w>0 and h>0:
            glUniform4f(self.uniforms["rawres"], w, h, 1.0/float(w),1.0/float(h))
        glUniform1f(self.uniforms["time"], 0)
        if activeArea==None:
            glUniform4f(self.uniforms["activeArea"],0.0,0.0,width,height)
        else:
            glUniform4f(self.uniforms["activeArea"],*activeArea)
        glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)



