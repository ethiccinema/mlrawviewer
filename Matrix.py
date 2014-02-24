import numpy as np
import math

import pyrr.matrix44
from pyrr.matrix44 import *

class Matrix4x4(object):
    def __init__(self):
        md = np.zeros(shape=(4,4),dtype=np.float32)
        m = np.matrix(md)
        self.m = m
        self.width = 2.0
        self.height = 2.0   
        self.identity()
    def copy(self,other):
        self.m = other.m
        self.width = other.width
        self.height = other.height
    def reset(self):
        self.identity()
    def identity(self):
        self.m[:,:] = 0.
        self.m[0,0]=1.
        self.m[1,1]=1.
        self.m[2,2]=1.
        self.m[3,3]=1.
        self.width = 2.0
        self.height = 2.0   
    def viewport(self,width,height):
        if hasattr(pyrr.matrix44,"create_orthogonal_view_matrix"):
             proj = create_orthogonal_view_matrix(0.0,width,0.0,height,0.0,1.0)
        else:
             proj = create_orthogonal_projection_matrix(0.0,width,0.0,height,0.0,1.0)
        self.m = multiply(proj,self.m)
        self.width = float(width)
        self.height = float(height)
    def scale(self,factor):
        scale = create_from_scale([factor,factor,1.0])
        self.m = multiply(scale,self.m)
    def scale2d(self,width,height):
        scale = create_from_scale([width,height,1.0])
        self.m = multiply(scale,self.m)
    def translate(self,x,y):
        trans = create_from_translation([x,y,0.0])
        self.m = multiply(trans,self.m)
    def rotation(self,angle):
        rot = create_from_z_rotation(angle)
        self.m = multiply(rot,self.m)
    def mult(self,matrix):
        self.m *= matrix.m 
    def multvec(self,x,y):
        return apply_to_vector(self.m,(x,y,0.0))
    def multveci(self,x,y):
        return apply_to_vector(inverse(self.m),(x,y,0.0))
    

