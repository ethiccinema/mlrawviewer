import numpy as np
import math

class Matrix4x4(object):
    def __init__(self):
        md = np.zeros(shape=(4,4),dtype=np.float32)
        m = np.matrix(md)
        self.m = m
        self.width = 2.0
        self.height = 2.0   
        self.identity()
    def reset(self):
        self.identity()
    def identity(self):
        self.m[:,:] = 0.
        self.m[0,0]=1.
        self.m[1,1]=1.
        self.m[2,2]=1.
        self.m[3,3]=1.
    def viewport(self,width,height):
        self.m[1,1] *= float(width)/float(height)
        self.width = float(width)
        self.height = float(height)
    def scale(self,factor):
        self.m[0,0] *= factor
        self.m[1,1] *= factor
    def translate(self,x,y):
        self.m[3,0] += x * 2.0/self.width 
        self.m[3,1] += y * 2.0/self.height 
    def rotation(self,angle):
        sa = math.sin(angle)
        ca = math.cos(angle)
        self.m[0,0] = ca
        self.m[1,0] = -sa
        self.m[0,1] = sa
        self.m[1,1] = ca
    def mult(self,matrix):
        self.m *= matrix.m 


