"""
ShaderGraph.py
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

Draw a graph or plot from a table supplied in a texture
Can be used either for histograms, or 1DLUT curves 
"""

import GLCompute
from OpenGL.GL import *
import numpy as np
import array

class ShaderGraph(GLCompute.Shader):
    vertex_src = """
attribute vec4 vertex;
varying vec2 texcoord;
uniform mat4 matrix;
uniform vec4 rawres;
void main() {
    vec4 coordinate = vec4(vertex.xy,0.0,1.0);
    vec4 position = matrix * coordinate;
    gl_Position = position;
    texcoord = vertex.zw;
}
"""
    fragment_src = """
uniform sampler2D tex;
uniform vec4 rawres;
varying vec2 texcoord;
uniform float opacity;

void main() {
    float v = texture2D(tex,texcoord).r;
    float b = step(1.0-texcoord.y,v*256.);
    float z = (0.25+0.75*b)*opacity;
    gl_FragColor = vec4(vec3(b)*z,z);
}
"""
    def __init__(self,**kwds):
        myclass = self.__class__
        super(ShaderGraph,self).__init__(myclass.vertex_src,myclass.fragment_src,["rawtex","rawres","matrix","tex","opacity"],**kwds)
        self.svbo = None
        self.samples = 0
    def prepare(self,svbo,width,height):
        if self.svbo==None:
            self.svbo = svbo
            self.svbobase = svbo.allocate(4*16)
            vertices = np.array((0,0,0,0,
                                 width,0,1,0,
                                 0,height,0,1,
                                 width,height,1,1),dtype=np.float32)
            self.svbo.update(vertices,self.svbobase)

    def draw(self,matrix,width,height,texture,opacity):
        self.use()
        self.blend(True)
        glVertexAttribPointer(self.vertex,4,GL_FLOAT,GL_FALSE,0,self.svbo.vboOffset(self.svbobase))
        glEnableVertexAttribArray(self.vertex)
        texture.bindtex(False)
        glUniform1i(self.uniforms["rawtex"], 0)
        glUniformMatrix4fv(self.uniforms["matrix"], 1, 0, matrix.m.tolist())
        glUniform1i(self.uniforms["tex"], 0)
        glUniform1f(self.uniforms["opacity"], opacity)
        w = width
        h = height
        if w>0 and h>0:
            glUniform4f(self.uniforms["rawres"], w, h, 1.0/float(w),1.0/float(h))
        glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)

