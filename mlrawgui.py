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
        self.labelBlack = tk.Label(self, text='Black Level', padx=10, pady=5)
        self.labelBlack.grid(row=2, column=0, columnspan=2)
        self.labelWhite = tk.Label(self, text='White Level', padx=10, pady=5)
        self.labelWhite.grid(row=2, column=2, columnspan=2)
        

        #row 3
        self.labelBrightness = tk.Label(self, text='Brightness:', padx=10, pady=5)
        self.labelBrightness.grid(row=3, column=0, sticky='W')
        
        self.spinBrightness = tk.Spinbox(self, from_=0, to=100, width=15, justify='right', wrap=True)
        self.spinBrightness.grid(row=3, column=1)
        
        #row 4
        self.labelRGB = tk.Label(self, text='RGB Multipliers:', padx=10, pady=5)
        self.labelRGB.grid(row=4, column=0, sticky='W')
        
        self.spinRed = tk.Spinbox(self, from_=0, to=8, width=15, justify='right', increment=0.2, wrap=True)
        self.spinRed.grid(row=4, column=1)
        
        self.spinGreen = tk.Spinbox(self, from_=0, to=8, width=15, justify='right', increment=0.2, wrap=True)
        self.spinGreen.grid(row=4, column=2)
        
        self.spinBlue = tk.Spinbox(self, from_=0, to=8, width=15, justify='right', increment=0.2, wrap=True)
        self.spinBlue.grid(row=4, column=3)


        self.BUTTON = tk.Button(self, text='TEST', command=self.TEST)
        self.BUTTON.grid(row=5, column=1, columnspan=2)
    def TEST(self):
        self.p.toggleAnamorphic()


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
            self.labelFPS['text'] = str(r.fps) + ' fps'
            self.labelFrames['text'] = str(r.frames()) + ' frames'

            self.labelBlack['text'] = 'Black level: ' + str(r.black)
            self.labelWhite['text'] = 'White level: ' + str(r.white)

            self.rawThread(r)
        except Exception, err:
            self.labelFilePath['text'] = 'Could not open file %s. Error:%s\n'%(afile,str(err))

    def rawThread(self, r):
        #self.p = mlrawviewer.launchFromGui(r)
        #self.p.run()

        self.p = multiprocessing.Process(target=mlrawviewer.launchFromGui, args=(r,))
        self.p.daemon = True
        self.p.start()
        #print self.p.is_alive()
        #self.p.run()

        #self.rmc = mlrawviewer.Viewer(r) 
        #return self.rmc.run()
        #return 0


if __name__ == '__main__':
    root = tk.Tk()
    app = Application(master=root)
    app.mainloop()
    try:
        root.destroy()
    except:
        pass
