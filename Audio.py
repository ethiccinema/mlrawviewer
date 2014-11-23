import threading,Queue,time

noAudio = True
try:
    import pyaudio
    noAudio = False
except Exception,err:
    print "pyAudio not available. Cannot play audio"

class Audio(object):
    INIT = 0
    PLAY = 1
    STOP = 2
    def __init__(self):
        global noAudio
        self.playThread = threading.Thread(target=self.audioLoop)
        self.playThread.daemon = True
        self.commands = Queue.Queue(1)
        self.currentParams = None
        if not noAudio:
            self.playThread.start()
    def init(self,sampleRate,sampleWidth,channels,samples):
        global noAudio
        if not noAudio:
            self.commands.put((Audio.INIT,(sampleRate,sampleWidth,channels,samples)))
    def play(self,offset):
        global noAudio
        if not noAudio:
            self.commands.put((Audio.PLAY,offset))
    def stop(self):
        global noAudio
        if not noAudio:
            self.commands.put((Audio.STOP,None))
    def audioLoop(self):
        pa = pyaudio.PyAudio()
        dataBuffer = None
        bufferOffset = 0
        frameSize = 0
        stream = None
        started = False
        while 1:
            if self.commands.empty() and dataBuffer != None and stream != None and bufferOffset<len(dataBuffer) and started:
                bufSize = 8 * 1024 * frameSize
                left = len(dataBuffer)-bufferOffset
                if bufferOffset<0:
                    try:
                        stream.write("\0"*(-bufferOffset),exception_on_underflow=True)
                    except:
                        import traceback
                        traceback.print_exc()
                        print "Audio underflow"
                        stream = None
                        dataBuffer = None
                    bufferOffset = 0
                elif left<bufSize:
                    try:
                        stream.write(dataBuffer[bufferOffset:],exception_on_underflow=True)
                    except:
                        import traceback
                        traceback.print_exc()
                        print "Audio underflow"
                        stream = None
                    bufferOffset = len(dataBuffer)
                else:
                    newoffset = bufferOffset+bufSize
                    try:
                        stream.write(dataBuffer[bufferOffset:newoffset],exception_on_underflow=True)
                    except:
                        import traceback
                        traceback.print_exc()
                        print "Audio underflow"
                        stream = None
                    bufferOffset = newoffset
            else:
                command = self.commands.get()
                commandType,commandData = command
                if commandType==Audio.INIT:
                    #print "Init",commandData[:3],len(commandData[3])
                    if stream == None or commandData != self.currentParams:
                        if stream != None: stream.close()
                        try:
                            sampleRate,sampleWidth,chn,dataBuffer = commandData
                            fmt = pa.get_format_from_width(sampleWidth)
                            stream = pa.open(format=fmt,channels=chn,rate=sampleRate,output=True,start=False)
                            frameSize = sampleWidth * chn
                            self.currentParams = commandData
                        except:
                            import traceback
                            traceback.print_exc()
                            stream = None
                            self.currentParams = None
                if commandType==Audio.PLAY:
                    # print "Play",commandData,len(dataBuffer)
                    bufferOffset = commandData
                    if stream == None:
                        fmt = pa.get_format_from_width(sampleWidth)
                        stream = pa.open(format=fmt,channels=chn,rate=sampleRate,output=True,start=False)
                    if stream != None and not started:
                        stream.start_stream()
                        started = True
                elif commandType==Audio.STOP:
                    # print "Stop"
                    if stream != None and started:
                        stream.stop_stream()
                        started = False


