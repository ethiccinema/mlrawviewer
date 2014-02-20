#!/usr/bin/python2.7
import os,sys,zlib
from PIL import Image
import numpy as np

icons = [fn for fn in os.listdir("../data/") if fn.lower().endswith(".png")]
icons.sort()

icondata = []
pixels = 0
for fn in icons:
    fulln = os.path.join("../data/",fn)
    i = Image.open(fulln)
    ia = np.fromstring(i.tostring(),dtype=np.uint8).reshape(128,128)
    icondata.append(ia)
    pixels += (ia.shape[0]*ia.shape[1])

nx = 128
ny = 128
availpixels = nx*ny
while availpixels<pixels:
    nx*=2
    ny*=2
    availpixels = nx*ny
    
atlas = np.zeros(shape=(ny,nx),dtype=np.uint8)
x,y=0,0
for ia in icondata:
    if x+ia.shape[1]>atlas.shape[1]:
        y+=ia.shape[0]
        x=0
    atlas[y:y+ia.shape[0],x:x+ia.shape[1]] += (255-ia)
    x += ia.shape[1]

file("../data/icons.z",'wb').write(zlib.compress(atlas.tostring()))


