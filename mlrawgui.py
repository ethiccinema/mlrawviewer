#!/usr/bin/python

import os
import sys
import multiprocessing

try:
    import tkinster as tk
except ImportError:
    import Tkinter as tk
import tkFileDialog

import mlrawviewer
import MlRaw

class Application(tk.Frame):
    def __init__(self, master=None):
        tk.Frame.__init__(self, master)
        self.master.title('MlRawViewer')

        self.grid()
        self.createWidgets()

    def createWidgets(self):
        self.menubar = tk.Menu(self)
        self.fileMenu = tk.Menu(self.menubar, tearoff=0)
        self.fileMenu.add_command(label='Open', command=self.openFile)
        self.fileMenu.add_separator()
        self.fileMenu.add_command(label='Exit', command=self.quit)
        self.menubar.add_cascade(label='File', menu=self.fileMenu)
        self.master.config(menu=self.menubar)
        
        
        #row 0
        self.labelFilePath = tk.Label(self, text='/../../..', padx=10, pady=5)
        self.labelFilePath.grid(row=0, column=0, columnspan=4, sticky='W')
        
        #row 1
        self.labelSize = tk.Label(self, text='Size', padx=10, pady=5)
        self.labelSize.grid(row=1, column=0, columnspan=2)
        self.labelFPS = tk.Label(self, text='FPS', padx=10, pady=5)
        self.labelFPS.grid(row=1, column=2)
        self.labelFrames = tk.Label(self, text='Frames', padx=10, pady=5)
        self.labelFrames.grid(row=1, column=3)

        #row 2
        self.labelBrightness = tk.Label(self, text='Brightness:', padx=10, pady=5)
        self.labelBrightness.grid(row=2, column=0, sticky='W')
        
        self.spinBrightness = tk.Spinbox(self, from_=0, to=100, width=15, justify='right', wrap=True)
        self.spinBrightness.grid(row=2, column=1)
        
        #row 3
        self.labelRGB = tk.Label(self, text='RGB Multipliers:', padx=10, pady=5)
        self.labelRGB.grid(row=3, column=0, sticky='W')
        
        self.spinRed = tk.Spinbox(self, from_=0, to=8, width=15, justify='right', increment=0.2, wrap=True)
        self.spinRed.grid(row=3, column=1)
        
        self.spinGreen = tk.Spinbox(self, from_=0, to=8, width=15, justify='right', increment=0.2, wrap=True)
        self.spinGreen.grid(row=3, column=2)
        
        self.spinBlue = tk.Spinbox(self, from_=0, to=8, width=15, justify='right', increment=0.2, wrap=True)
        self.spinBlue.grid(row=3, column=3)

    def openFile(self):
        mlFileTypes = ('*.MLV', '*.mlv', '*.RAW', '*.raw')
        afile = tkFileDialog.askopenfilename(title='Open ML video...', initialdir='~/Videos', filetypes=[('ML', mlFileTypes)])
        if afile != None:
            self.rawFile(afile)

    def rawFile(self, afile):
        try:
            r = MlRaw.loadRAWorMLV(afile)
            self.labelFilePath['text'] = str(afile)
            self.labelSize['text'] = str(r.width()) + ' x ' + str(r.height())
            self.labelFrames['text'] = str(r.frames()) + ' frames'
            self.rawThread(r)
        except Exception, err:
            self.labelFilePath['text'] = 'Could not open file %s. Error:%s\n'%(afile,str(err))

    def rawThread(self, r):
        p = multiprocessing.Process(target=mlrawviewer.launchFromGui, args=(r,))
        #p = multiprocessing.Process(target=self.fakeLoop)
        p.daemon = True
        p.start()
        print p.is_alive()

        #self.rmc = mlrawviewer.Viewer(r) 
        #return self.rmc.run()
        #return 0

    def fakeLoop(self):
        while True:
            print 0


class FakeClass:
    pass


if __name__ == '__main__':
    root = tk.Tk()
    app = Application(master=root)
    app.mainloop()
    try:
        root.destroy()
    except:
        pass
