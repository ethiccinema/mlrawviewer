import numpy as np
import math

def multiply(ma,mb):
    return np.dot(ma,mb)

def identity():
    return np.matrix(np.identity( 4, dtype=np.float32))

class Matrix4x4(object):
    def __init__(self):
        self.m = identity()
    def copy(self,other):
        self.m = other.m
    def reset(self):
        self.identity()
    def identity(self):
        self.m = identity()
    def viewport(self,width,height):
        proj = identity()
        proj[0,0] = 2.0/width
        proj[1,1] = -2.0/height
        proj[2,2] = -2.0
        self.m = multiply(proj,self.m)
    def scale(self,factor):
        scale = identity() 
        scale[0,0] = factor
        scale[1,1] = factor
        self.m = multiply(scale,self.m)
    def scale2d(self,width,height):
        scale = identity() 
        scale[0,0] = width
        scale[1,1] = height
        self.m = multiply(scale,self.m)
    def translate(self,x,y):
        trans = identity() 
        trans[3,:2] = [x,y]
        self.m = multiply(trans,self.m)
    def rotation(self,angle):
        rot = identity() 
        ca = math.cos(angle)
        sa = math.sin(angle)
        rot[:2,:2] = np.array([[ca,-sa],[sa,ca]])
        self.m = multiply(rot,self.m)
    def mult(self,matrix):
        self.m *= matrix.m 
    def multvec(self,x,y):
        v = np.array((x,y,0.0,1.0))
        r = np.empty(shape=(4,))
        r[:] = np.dot(v,self.m)[0,:]
        if r[3] != 0.0: r = r/r[3]
        return r[:3]
    def multveci(self,x,y):
        m = self.m.getI()
        v = np.array([x,y,0.0,1.0])
        r = np.empty(shape=(4,))
        r[:] = np.dot(v,m)[0,:]
        if r[3] != 0.0: r = r/r[3]
        return r[:3]
    

