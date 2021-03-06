"""
ShaderText.py
(c) Andrew Baldwin 2013-2014

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
from OpenGL.arrays import vbo
import numpy as np

class ShaderText(GLCompute.Shader):
    vertex_src = """
attribute vec4 axyuv;
attribute vec4 argba;
attribute vec4 actmg;
varying vec2 texcoord;
uniform mat4 matrix;
uniform vec4 urgba;
uniform vec4 whxy;
varying vec4 rgba;
varying vec4 ctmg;
void main() {
    vec4 coordinate = vec4(axyuv.xy,0.0,1.0);
    vec4 position = matrix * coordinate;
    gl_Position = position;
    texcoord = axyuv.zw;
    rgba = argba;
    ctmg = actmg;
}
"""
    fragment_src = """
uniform sampler2D tex;
varying vec2 texcoord;
varying vec4 rgba;
varying vec4 ctmg;
uniform vec4 urgba;
uniform vec4 whxy;

void main() {
    vec4 t = texture2D(tex,texcoord).rgba;
    vec4 tr = vec4(t.r);
    t = mix(tr,t,ctmg.y);
    float r = 1.0;
    if (any(greaterThan(whxy.zw,vec2(0.0)))) {
        vec2 tx = (1.0 - abs((texcoord - 0.5)*2.0)); // Change to 1 at centre, 0 at edges
        vec2 pxy = smoothstep(vec2(0.0),whxy.zw,tx);
        r = pxy.x*pxy.y;
    }
    vec4 col = ctmg.x*rgba + (1.0-ctmg.z)*t + ctmg.z*t*rgba;
    gl_FragColor = r*urgba*pow(col,vec4(ctmg.w));
}
"""

    def __init__(self,font,**kwds):
        myclass = self.__class__
        super(ShaderText,self).__init__(myclass.vertex_src,myclass.fragment_src,["urgba","matrix","tex","whxy"],**kwds)
        self.axyuv = glGetAttribLocation(self.program, "axyuv")
        self.argba = glGetAttribLocation(self.program, "argba")
        self.actmg = glGetAttribLocation(self.program, "actmg")
        self.font = font
    def draw(self,vab,texture,matrix,rgba=(1.0,1.0,1.0,1.0),opacity=1.0,whxy=(1.0,1.0,0.0,0.0)):
        #print "draw",vab,texture,rgba,opacity,matrix.m
        self.use()
        glEnableVertexAttribArray(self.axyuv)
        glVertexAttribPointer(self.axyuv,4,GL_FLOAT,GL_FALSE,48,vab[0])
        glEnableVertexAttribArray(self.argba)
        glVertexAttribPointer(self.argba,4,GL_FLOAT,GL_FALSE,48,vab[1])#vertices+16)
        glEnableVertexAttribArray(self.actmg)
        glVertexAttribPointer(self.actmg,4,GL_FLOAT,GL_FALSE,48,vab[2])#vertices+32)
        if texture:
            texture.bindtex(True) # Use linear filter
        else:
            GLCompute.Texture.unbindtex(context=self.context)
        glUniform4f(self.uniforms["urgba"], rgba[0]*opacity,rgba[1]*opacity,rgba[2]*opacity,rgba[3]*opacity)
        glUniformMatrix4fv(self.uniforms["matrix"], 1, 0, matrix.m.tolist())
        glUniform1i(self.uniforms["tex"], 0)
        glUniform4f(self.uniforms["whxy"], whxy[0],whxy[1],whxy[2],whxy[3])
        #glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        self.blend(True)
        glDrawArrays(GL_TRIANGLES, 0, vab[3])#len(vertices)/12)

    def gradient(self,width,height,tl,tr,bl,br):
        uv=(0.0,0.0,1.0,1.0)
        triangles = 2
        v = np.zeros(shape=(triangles*3,12),dtype=np.float32)
        v[:,8] = 1.0 # Use colour only
        v[:,9] = 0.0 # Use texture
        v[:,10] = 0.0 # Use tint
        v[:,11] = 0.8 # Gamma
        x0 = 0.0
        y0 = 0.0
        x1 = float(width)
        y1 = float(height)
        u0 = uv[0]
        v1 = uv[1]
        u1 = uv[0]+uv[2]
        v0 = uv[1]+uv[3]
        vp = 0
        v[vp,:4] = [x0,y0,u0,v1]
        v[vp,4:8] = tl
        vp += 1
        v[vp,:4] = [x1,y0,u1,v1]
        v[vp,4:8] = tr
        vp += 1
        v[vp,:4] = [x0,y1,u0,v0]
        v[vp,4:8] = bl
        vp += 1
        v[vp,:4] = [x0,y1,u0,v0]
        v[vp,4:8] = bl
        vp += 1
        v[vp,:4] = [x1,y0,u1,v1]
        v[vp,4:8] = tr
        vp += 1
        v[vp,:4] = [x1,y1,u1,v0]
        v[vp,4:8] = br
        vp += 1
        v = v.reshape((v.shape[0]*v.shape[1],))
        return (None,v)
    def rectangle(self,width,height,rgba=(1.0,1.0,1.0,1.0),uv=(0.0,0.0,1.0,1.0),solid=1.0,tex=0.0,tint=0.0,texture=None):
        triangles = 2
        v = np.zeros(shape=(triangles*3,12),dtype=np.float32)
        v[:,4:8] = rgba
        v[:,8] = solid # Use colour only
        v[:,9] = tex # Use texture
        v[:,10] = tint # Use tint
        v[:,11] = 0.8 # Gamma
        x0 = 0.0
        y0 = 0.0
        x1 = float(width)
        y1 = float(height)
        u0 = uv[0]
        v1 = uv[1]
        u1 = uv[0]+uv[2]
        v0 = uv[1]+uv[3]
        vp = 0
        v[vp,:4] = [x0,y0,u0,v1]
        vp += 1
        v[vp,:4] = [x1,y0,u1,v1]
        vp += 1
        v[vp,:4] = [x0,y1,u0,v0]
        vp += 1
        v[vp,:4] = [x0,y1,u0,v0]
        vp += 1
        v[vp,:4] = [x1,y0,u1,v1]
        vp += 1
        v[vp,:4] = [x1,y1,u1,v0]
        vp += 1
        v = v.reshape((v.shape[0]*v.shape[1],))
        return (texture,v)

    def label(self,text,rgba=(1.0,1.0,1.0,1.0),linespace=70):
        lw = 0
        lh = linespace
        f = self.font
        kerning = 0
        pi = None
        x = 0
        y = 0
        x0 = 0
        y0 = 0
        v = np.zeros(shape=(len(text)*6,12),dtype=np.float32)
        v[:,4:8] = rgba
        v[:,8] = 0 # Use colour only
        v[:,9] = 0 # Red (font gray) only 
        v[:,10] = 0 # Use tint
        v[:,11] = 0.8 # Gamma

        vp = 0
        k = f.kerning
        g = f.geometry
        for c in text:
            ci = ord(c)
            if ci>0xFF:
                continue
            if ci==10: # new line
                x = 0
                y += linespace
                lh += linespace
                continue
            if pi:
                kernkey = (pi<<8) + ci
                kerning = k.get(kernkey,0)/64.0
                #print kernkey,kerning
            # oy,ox,h,w,l,t,ax,ay =
            #g = f.geometry[:,ci]
            #oy,ox,h,w,l,t,ax,ay = g[:,ci]

            oy = g.item((0,ci))
            ox = g.item((1,ci))
            h = g.item((2,ci))
            w = g.item((3,ci))
            l = g.item((4,ci))
            t = g.item((5,ci))
            ax = g.item((6,ci))
            ay = g.item((7,ci))

            #print ci,f.geometry[:,ci]
            """
            x0 = x + l + kerning - ox + 2.0
            y0 = y - h + t - oy + 2.0
            x1 = x0 + 60.0
            y1 = y0 + 60.0
            tx = (64.0*(ci%16)+2.0)/1024.0
            ty = (64.0*(ci/16)+2.0)/1024.0
            """
            x0 = x + l + kerning - 4.0
            y0 = y + (50 - t) - 4.0
            x1 = x0 + w + 8.0
            lw = max(x1,lw)
            y1 = y0 + h + 8.0
            tx = (64.0*(ci%16)+ox-4.0)/1024.0
            ty = (64.0*(ci/16)+oy-4.0)/1024.0

            u0 = tx
            v1 = ty
            u1 = tx + (w+8.0)/1024.0
            v0 = ty + (h+8.0)/1024.0
#            u1 = tx + (60.0)/1024.0
#            v1 = ty + (60.0)/1024.0
            #print x0,y0,u0,v0,x1,y1,u1,v1,ax/64.0,ay/64.0,kerning
            v[vp,0] = x0
            v[vp,1] = y0
            v[vp,2] = u0
            v[vp,3] = v1
            vp += 1
            v[vp,0] = x1
            v[vp,1] = y0
            v[vp,2] = u1
            v[vp,3] = v1
            vp += 1
            v[vp,0] = x0
            v[vp,1] = y1
            v[vp,2] = u0
            v[vp,3] = v0
            vp += 1
            v[vp,0] = x0
            v[vp,1] = y1
            v[vp,2] = u0
            v[vp,3] = v0
            vp += 1
            v[vp,0] = x1
            v[vp,1] = y0
            v[vp,2] = u1
            v[vp,3] = v1
            vp += 1
            v[vp,0] = x1
            v[vp,1] = y1
            v[vp,2] = u1
            v[vp,3] = v0
            vp += 1
            x += ax/64.0 + kerning
            y += ay/64.0
            pi = ci
        v = v.reshape((v.shape[0]*v.shape[1],))
        return (f.texture(),v,lw,lh)

