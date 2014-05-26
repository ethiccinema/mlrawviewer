#!/usr/bin/python2.7

"""
All dialogs are here to be run from seperate process
"""

import sys

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
    return ret

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

if __name__ == '__main__':
    dialogType = sys.argv[1]
    initial = sys.argv[2]
    if dialogType=="okToExit":
        print okToExit()
    elif dialogType=="chooseOutputDir":
        print chooseOutputDir(initial)
    elif dialogType=="openFilename":
        print openFilename(initial)

