#/usr/bin/python2
import sys,os,math,array

# So we can use modules from the main dir
root = os.path.split(sys.path[0])[0]
sys.path.append(root)

import bitunpack

inj = file(sys.argv[1],'r').read()
inj2 = file(sys.argv[2],'r').read()
width = int(sys.argv[3])
height = int(sys.argv[4])

image = array.array('H',"\0\0"*width*height)

bitunpack.unpackljto16(inj,image,0,width/2,width/2,array.array('H',range(4096)).tostring())
bitunpack.unpackljto16(inj2,image,width,width/2,width/2,array.array('H',range(4096)).tostring())

outf = file(sys.argv[5],'wb')
outf.write("P5 %d %d 4095\n"%(width,height))
image.byteswap()
outf.write(image)
outf.close()

