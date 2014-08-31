"""
ShaderHistogram.py
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

Sample the image at all supplied vertices (points) in vertex shader,
and transform coordinates to the right bin n a small horizontal accumulation texture
"""

import GLCompute
from OpenGL.GL import *
import numpy as np
import array

class ShaderHistogram(GLCompute.Shader):
    vertex_src = """
attribute vec2 vertex;
uniform vec4 rawres;
uniform sampler2D rawtex;
void main() {
    vec3 rgb = texture2D(rawtex,vertex.xy).rgb;
    vec2 pos = vec2(rgb.r*2.0-1.,0.5);
    gl_Position = vec4(pos.xy,0.0,1.0);
}
"""
    fragment_src = """
uniform vec4 rawres;

void main() {
    gl_FragColor = vec4(1.0/65535.0);
}
"""

    def __init__(self,**kwds):
        myclass = self.__class__
        super(ShaderHistogram,self).__init__(myclass.vertex_src,myclass.fragment_src,["rawtex","rawres"],**kwds)
        self.svbo = None
        self.samples = 0
    def prepare(self,svbo,width,height):
        if self.svbo==None:
            self.svbo = svbo
            self.svbobase = svbo.allocate(width*height)
            yinc = 1.0/float(height)
            xinc = 1.0/float(width)
            vertices = array.array('f')
            cy = yinc/2.0
            for y in range(height):
                cx = xinc/2.0
                for x in range(width):
                    vertices.extend((cx,cy))
                    cx += xinc
                cy += yinc
            self.svbo.update(np.array(vertices,dtype=np.float32),self.svbobase)
            self.samples = width*height

    def draw(self,width,height,texture):
        self.use()
        self.blend(False)
        glVertexAttribPointer(self.vertex,2,GL_FLOAT,GL_FALSE,0,self.svbo.vboOffset(self.svbobase))
        glEnableVertexAttribArray(self.vertex)
        texture.bindtex(False)
        glUniform1i(self.uniforms["rawtex"], 0)
        w = width
        h = height
        if w>0 and h>0:
            glUniform4f(self.uniforms["rawres"], w, h, 1.0/float(w),1.0/float(h))
        glClear(GL_COLOR_BUFFER_BIT)
        glEnable(GL_BLEND)
        glBlendFunc(GL_ONE,GL_ONE)
        glDrawArrays(GL_POINTS, 0, self.samples)

