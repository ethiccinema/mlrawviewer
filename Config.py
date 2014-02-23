"""
Config.py
(c) Andrew Baldwin 2014

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
of the Software, and to permit persons to whom the Software is furnished to do
so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

Cross-platform configuration
Persist state 
Check for updates of the app

"""

import sys,urllib2
from threading import Thread

PLAT_SRC = 0
PLAT_MAC = 1
PLAT_WIN = 2

UPDATE_URL_BASE = "https://bitbucket.org/baldand/mlrawviewer/src/master/data/"

class Config(object):
    def __init__(self,version,**kwds):
        super(Config,self).__init__(**kwds)
        self.version = version
        p = sys.platform
        self.platform = PLAT_MAC # PLAT_SRC
        if p.startswith("darwin"):
            self.platform = PLAT_MAC
        elif p.startswith("win"):
            self.platform = PLAT_WIN
        self.updateThread = None
        self.updateVersion = None
        self.checkForUpdate()
    def version(self):
        return self.version
    def versionString(self):
        return ".".join((str(v) for v in self.version))
    def isUpdateAvailable(self):
        return self.updateVersion
    def checkIfNewer(self,data):
        try:
            posver = data.split()[0].split(".")
            if len(posver>=3):
                newer = False
                uv = []
                for i in range(3):
                    v = self.version[i]
                    u = int(posver[i])
                    if u>v: newer = True
                    uv.append(u)
                if newer:
                    self.updateVersion = uv
                    print "Update version available:",self.updateVersion
        except:
            pass
    def updateThreadFunction(self):
        print "updatethreadFunction"
        if self.isMac():
            url = UPDATE_URL_BASE + "current_mac_version"
        elif self.isWin():
            url = UPDATE_URL_BASE + "current_win_version"
        else: 
            self.updateThread = None
            return 
        print "urlopen"
        try:
            result = urllib2.urlopen(url)
            print "urlreturned"
            if result.getcode()==200:
                self.checkIfNewer(result.read())
        except:
            print "urlopen error"
            pass
        self.updateThread = None
    def checkForUpdate(self):
        if self.platform == PLAT_SRC: return
        if self.updateThread == None:
            self.updateThread = Thread(target=self.updateThreadFunction)
            self.updateThread.daemon = True
            self.updateThread.start()
    def isMac(self):
        return self.platform == PLAT_MAC
    def isWin(self):
        return self.platform == PLAT_WIN
