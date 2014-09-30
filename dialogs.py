#!/usr/bin/python2.7

"""
All dialogs are here to be run from seperate process
"""

import sys,re

# python tkinter imports
try:
    import Tkinter as tk #python2
except ImportError:
    import tkinter as tk #python3
import tkFileDialog
import tkMessageBox

root = tk.Tk()
root.iconify()

def okToExit():
    ret = tkMessageBox.askyesno("Exit","Cancel export and exit?")
    if ret:
        return "True"
    else:
        return "False"

def chooseOutputDir(initialDir):
    adir = tkFileDialog.askdirectory(title='Choose DNG or ProRes output directory...', initialdir=initialDir)
    return adir

def openFilename(initialDir):
    mlFT1 = ('*.RAW', '*.raw')
    mlFT2 = ('*.MLV', '*.mlv')
    mlFT3 = ('*.DNG', '*.dng')
    mlFileTypes = [('ML', mlFT1 + mlFT2 + mlFT3), ('RAW', mlFT1), ('MLV', mlFT2), ('DNG', mlFT3), ('All', '*.*')]
    afile = tkFileDialog.askopenfilename(title='Open ML video...', initialdir=initialDir, filetypes=mlFileTypes)
    return afile

def importLuts():
    mlFT1 = ('*.cube', '*.CUBE')
    mlFileTypes = [('CUBE', mlFT1), ('All', '*.*')]
    afiles = tkFileDialog.askopenfilename(title='Choose LUT files to import...', filetypes=mlFileTypes, multiple=1)
    if type(afiles)!=tuple:
        # Workaround for windows bug... result is tk string.
        # If a filename had spaces, it has { } around it, else it doesn't
        sep = re.findall("{.*?}|\S+",afiles)
	afiles = [re.sub("^{|}$","",i) for i in sep]
    return afiles

if __name__ == '__main__':
    import codecs
    fromUtf8=codecs.getdecoder('UTF8')
    toUtf8=codecs.getencoder('UTF8')

    dialogType = sys.argv[1]
    initial = unicode(fromUtf8(sys.argv[2])[0])
    if dialogType=="okToExit":
        sys.stdout.write(okToExit())
    elif dialogType=="chooseOutputDir":
        e = toUtf8(chooseOutputDir(initial))
        sys.stdout.write(e[0])
    elif dialogType=="openFilename":
	    e = toUtf8(openFilename(initial))
	    sys.stdout.write(e[0])
    elif dialogType=="importLut":
        e = importLuts()
        for f in e:
            sys.stdout.write(f)
            sys.stdout.write('\n')

