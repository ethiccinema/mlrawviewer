"""
ExportQueue.py
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
"""

import os,threading,Queue,time

class ExportQueue(threading.Thread):
    """
    Process a queue of export jobs one at a time but as quickly as possible
    Could be any kind of export in future - DNG, LinearDNG (demosacing), ProRes encode...
    For now, just DNG
    """
    JOB_DNG = 0
    def __init__(self,**kwds):
        super(ExportQueue,self).__init__(**kwds)
        self.iq = Queue.Queue()
        self.oq = Queue.Queue()
        self.jobs = {}
        self.jobstatus = {}
        self.jobindex = 0
        self.endflag = False
        self.ended = False
        self.busy = False
        self.start()
    def end(self):
        self.endflag = True
        self.iq.put(None)
    def hasEnded(self):
        return self.ended
    def waitForEnd(self):
        self.join()
    # Job status
    def status(self,index):
        if index >= self.jobindex:
            return 0.0
        elif index in self.jobstatus:
            return self.jobstatus[index]
        else:
            return 1.0
    # Queue Job calls
    def exportDng(self,rawfile,dngdir,startFrame=0,endFrame=None):
        return self.submitJob(self.JOB_DNG,rawfile,dngdir,startFrame,endFrame)
    def submitJob(self,*args):
        ix = self.jobindex
        self.jobindex += 1
        self.jobstatus[ix] = 0.0
        job = tuple([ix]+list(args))
        self.jobs[ix] = job
        self.iq.put(ix)
        return ix
    def run(self):
        try:
            while 1: # Wait for the next job in the Queue
                if self.endflag:
                    break
                jobindex = self.iq.get()
                if jobindex != None:
                    self.busy = True
                    self.nextJob(self.jobs[jobindex])
                    del self.jobs[jobindex]
                    del self.jobstatus[jobindex]
                    self.busy = False
        except:
            pass
        self.ended = True
    def nextJob(self,job):
        # Runs on processing thread
        jobType = job[1]
        jobArgs = job[2:]
        if jobType == self.JOB_DNG:
            self.doExportDng(job[0],jobArgs)
        else:
            pass
    def doExportDng(self,jobindex,args):
        print "doExportDng",args
        for i in range(100):
            time.sleep(0.1)            
            self.jobstatus[jobindex] = float(i)/100.0
            if self.endflag:
                break

