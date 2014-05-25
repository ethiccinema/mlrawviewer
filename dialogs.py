#!/usr/bin/python2.7

"""
All dialogs are here to be run from seperatre process
"""

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

def openFilename(initialDir,fileTypes):
    afile = tkFileDialog.askopenfilename(title='Open ML video...', initialdir=initialDir, filetypes=fileTypes)
    return afile
