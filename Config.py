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

import sys,urllib2,os.path,time,cPickle
from threading import Thread

PLAT_SRC = 0
PLAT_MAC = 1
PLAT_WIN = 2

UPDATE_URL_BASE = "https://bitbucket.org/baldand/mlrawviewer/raw/master/data/"

CONFIG_PATH = "~/.mlrawviewer"

TIME_BETWEEN_UPDATE_CHECKS = 3600.0 * 24.0 # 1 day

def verToStr(ver):
    return ".".join((str(v) for v in ver))

def dataToVer(old,data):
    try:
        posver = data.split()[0].split(".")
        if len(posver)>=3:
            newer = False
            older = False
            uv = []
            for i in range(3):
                v = old[i]
                u = int(posver[i])
                if u>v: newer = True
                if u<v: older = True
                uv.append(u)
            if newer and not older:
                return uv
    except:
        import traceback
        traceback.print_exc()
        pass
    return None

class Config(object):
    def __init__(self,version,**kwds):
        super(Config,self).__init__(**kwds)
        os.stat_float_times(True)
        self.version = version
        p = sys.platform
        self.platform = PLAT_SRC
        if p.startswith("darwin"):
            self.platform = PLAT_MAC
        elif p.startswith("win"):
            self.platform = PLAT_WIN
        self.updateThread = None
        self.updateVersion = None
        self.updateClicked = None
        self.createConfigDir()
        self.readUpdateClicked()
        self.checkForUpdate()
    def logFilePath(self):
        self.createConfigDir()
        return os.path.join(os.path.expanduser(CONFIG_PATH),"mlrawviewer.log")
    def setState(self,varname,value,raw=False):
        varFileName = os.path.join(self.configPath,varname)
        try:
            varFile = file(varFileName,'wb')
            if not raw: # USe a pickle
                cPickle.dump(value,varFile,cPickle.HIGHEST_PROTOCOL)
            else:
                varFile.write(value) # Better be text!
            varFile.close()
        except:
            pass
    def getState(self,varname,raw=False):
        varFileName = os.path.join(self.configPath,varname)
        result = None
        try:
            if os.path.exists(varFileName):
                varFile = file(varFileName,'rb')
                if not raw:
                    result = cPickle.load(varFile)
                else:
                    result = varFile.read()
                varFile.close()
        except:
            pass
        return result

    def createConfigDir(self):
        self.configPath = os.path.expanduser(CONFIG_PATH)
        if not os.path.exists(self.configPath):
            os.mkdir(self.configPath)
    def readUpdateClicked(self):
        updateClicked = os.path.join(self.configPath,"updateClicked")
        if os.path.exists(updateClicked):
            f = file(updateClicked,'rb')
            data = f.read()
            f.close()
            self.updateClicked = dataToVer((0,0,0),data)
    def updateClickedNow(self):
        updateClicked = os.path.join(self.configPath,"updateClicked")
        f = file(updateClicked,'wb')
        f.write(self.updateVersionString())
        f.close()
        self.updateClicked = self.updateVersion
    def version(self):
        return self.version
    def versionString(self):
        return verToStr(self.version)
    def updateVersionString(self):
        if self.updateVersion != None:
            return verToStr(self.updateVersion)
        else:
            return ""
    def isUpdateAvailable(self):
        return self.updateVersion
    def versionUpdateClicked(self):
        return self.updateClicked
    def checkIfNewer(self,data):
        uv = dataToVer(self.version,data)
        if uv != None:
            self.updateVersion = uv
            print "Updated version "+verToStr(uv)+" available from https://bitbucket.org/baldand/mlrawviewer/downloads"
            updateVersionFilename = os.path.join(self.configPath,"updateVersion")
            updateVersionFile = file(updateVersionFilename,'wb')
            updateVersionFile.write(data)
            updateVersionFile.close()
    def updateThreadFunction(self):
        if self.isMac():
            url = UPDATE_URL_BASE + "current_mac_version"
        elif self.isWin():
            url = UPDATE_URL_BASE + "current_win_version"
        else:
            self.updateThread = None
            return
        try:
            result = urllib2.urlopen(url)
            if result.getcode()==200:
                self.checkIfNewer(result.read())
        except:
            pass
        self.updateThread = None
    def checkForUpdate(self):
        if self.platform == PLAT_SRC: return
        if self.updateThread == None:
            updateVersionFilename = os.path.join(self.configPath,"updateVersion")
            check = False
            if not os.path.exists(updateVersionFilename):
                check = True
            else:
                lastUpdate = os.stat(updateVersionFilename).st_mtime
                now = time.time()
                if now > (lastUpdate + TIME_BETWEEN_UPDATE_CHECKS):
                    check = True
            if check:
                #print "Doing update check"
                self.updateThread = Thread(target=self.updateThreadFunction)
                self.updateThread.daemon = True
                self.updateThread.start()
            else:
                #print "Not doing update check"
                updateVersionFile = file(updateVersionFilename,'rb')
                data = updateVersionFile.read()
                updateVersionFile.close()
                self.checkIfNewer(data)
    def isMac(self):
        return self.platform == PLAT_MAC
    def isWin(self):
        return self.platform == PLAT_WIN

config = Config(version=(1,3,3))
