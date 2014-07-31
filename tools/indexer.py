#!/usr/bin/python2.7
"""
Index all found MLV files in a tree
"""
# standard python imports. Should not be missing
import sys,struct,os,math,time,datetime

# So we can use modules from the main dir
root = os.path.split(sys.path[0])[0]
sys.path.append(root)

# Now import our own modules
import MlRaw

def indexFile(filename):
    print "Loading",filename
    r = MlRaw.loadRAWorMLV(filename)
    stat = r.indexingStatus()
    informed = False
    while stat<1.0:
        time.sleep(0.1)
        stat = r.indexingStatus()
        out = "%.0f%%"%(stat*100.0)
        if stat<1.0:
            if not informed:
                print "Indexing:"   
                informed = True
            out += "..."
        if stat==1.0:
            break
        sys.stdout.write("\r\x1b[K"+out.__str__())
        sys.stdout.flush()

def findMlv(root):
    for dirpath,dirnames,filenames in os.walk(root):
        mlvs = [fn for fn in filenames if fn.lower().endswith(".mlv")]
        if len(mlvs)>0:
            print dirpath,len(mlvs)
            for fn in mlvs:
                fullpath = os.path.join(dirpath,fn)
                indexFile(fullpath)

if __name__ == '__main__':
    sys.exit(findMlv(sys.argv[1]))
