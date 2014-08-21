"""
ShaderDemosaic.py
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

from OpenGL.GL import *
import GLCompute
import numpy as np

"""
Note:

In lots of cases we do log2 on a raw value, then exp2 later.
This is so we do all interpolation operations in log
space, and gives better results especially in regions
where the intensity changes rapidly by orders of magnitude.

"""
class ShaderDemosaic(GLCompute.Shader):
    size_minus_one = True
    def __init__(self,**kwds):
        myclass = self.__class__
        super(ShaderDemosaic,self).__init__(myclass.vertex_src,myclass.fragment_src,["time","rawtex","rawres","black","colourBalance","tonemap","colourMatrix","lut","lutcontrol"],**kwds)
        self.svbo = None
    def preValidateConfig(self):
        # Must set up locations for sampler uniforms else validation errors in program
        self.use()
        glUniform1i(self.uniforms["rawtex"], 0)
        glUniform1i(self.uniforms["lut"], 1)
    def prepare(self,svbo):
        if self.svbo==None:
            self.svbo = svbo
            self.svbobase = svbo.allocate(4*12)
            vertices = np.array((-1,-1,0,1,-1,0,-1,1,0,1,1,0),dtype=np.float32)
            self.svbo.update(vertices,self.svbobase)

    def demosaicPass(self,texture,lut,black,time=0,balance=(1.0,1.0,1.0,1.0),white=(2**14-1),tonemap=1,colourMatrix=np.matrix(np.eye(3)),recover=1.0):
        self.use()
        self.blend(False)
        glVertexAttribPointer(self.vertex,3,GL_FLOAT,GL_FALSE,0,self.svbo.vboOffset(self.svbobase))
        glEnableVertexAttribArray(self.vertex)
        texture.bindtex(False,0)
        if lut!=None:
            lut.bindtex(texnum=1)
        glUniform1f(self.uniforms["tonemap"], float(tonemap))
        glUniform1i(self.uniforms["rawtex"], 0)
        glUniform1i(self.uniforms["lut"], 1)
        glUniform4f(self.uniforms["colourBalance"], balance[0], balance[1],balance[2],balance[3])
        glUniform4f(self.uniforms["black"], float(black)/(2**16-1),float(white)/(2**16-1),recover,0.0)
        if lut != None:
            glUniform4f(self.uniforms["lutcontrol"], lut.size, 0.0, 0.0, 0.0)
        else:
            glUniform4f(self.uniforms["lutcontrol"], 0.0, 0.0, 0.0, 0.0)
        w = texture.width
        h = texture.height
        if self.__class__.size_minus_one:
            w = w-1
            h = h-1
        iw = 1.0/float(w)
        ih = 1.0/float(h)
        glUniformMatrix3fv(self.uniforms["colourMatrix"], 1, False, np.array(colourMatrix.flatten()).astype(np.float32))
        glUniform4f(self.uniforms["rawres"], w, h, iw, ih)
        glUniform1f(self.uniforms["time"], time)
        glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)

