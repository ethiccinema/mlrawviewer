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

class ShaderDisplaySimple(GLCompute.Shader):
    vertex_src = """
attribute vec4 vertex;
varying vec2 texcoord;
uniform float time;
uniform vec3 colourBalance;
uniform vec4 rawres;
void main() {
    gl_Position = vertex;
    texcoord = (vec2(.5*vertex.x+.5,.5+.5*vertex.y));
}
"""
    fragment_src = """
varying vec2 texcoord;
uniform float time;
uniform vec3 colourBalance;
uniform vec4 rawres;
uniform sampler2D tex;

void main() {
    vec3 col = colourBalance*texture2D(tex,texcoord).rgb;
    gl_FragColor = vec4(col,1.);
}
"""

    def __init__(self,**kwds):
        myclass = self.__class__
        super(ShaderDisplaySimple,self).__init__(myclass.vertex_src,myclass.fragment_src,["time","tex","rawres","colourBalance"],**kwds)
    def draw(self,width,height,texture,balance):
        self.use()
        vertices = GLCompute.glarray(GLfloat,(-1,-1,0,1,-1,0,-1,1,0,1,1,0))
        glVertexAttribPointer(self.vertex,3,GL_FLOAT,GL_FALSE,0,vertices)
        glEnableVertexAttribArray(self.vertex)
        texture.bindtex(True) # Use linear filter
        glUniform1i(self.uniforms["tex"], 0)
        glUniform3f(self.uniforms["colourBalance"], balance[0], balance[1],balance[2])
        w = width
        h = height
        glUniform4f(self.uniforms["rawres"], w, h, 1.0/float(w),1.0/float(h))
        glUniform1f(self.uniforms["time"], 0)
        glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)
         
    

