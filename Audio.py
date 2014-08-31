import threading,Queue

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
        if not noAudio:
            self.playThread.start()
    def init(self,sampleRate,sampleWidth,channels):
        global noAudio
        if not noAudio:
            self.commands.put((Audio.INIT,(sampleRate,sampleWidth,channels)))
    def play(self,data):
        global noAudio
        if not noAudio:
            self.commands.put((Audio.PLAY,data))
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
        while 1:
            if self.commands.empty() and dataBuffer != None and stream != None:
                bufSize = 1024 * frameSize
                left = len(dataBuffer)-bufferOffset
                if left<bufSize:
                    stream.write(dataBuffer[bufferOffset:])
                    dataBuffer = None
                else:
                    newoffset = bufferOffset+bufSize
                    stream.write(dataBuffer[bufferOffset:newoffset])
                    bufferOffset = newoffset
            else:
                command = self.commands.get()
                commandType,commandData = command
                if commandType==Audio.INIT:
                    # print "Init",commandData
                    if stream == None:
                        try:
                            sampleRate,sampleWidth,chn = commandData
                            fmt = pa.get_format_from_width(sampleWidth)
                            stream = pa.open(format=fmt,channels=chn,rate=sampleRate,output=True,start=False)
                            frameSize = sampleWidth * chn
                        except:
                            import traceback
                            traceback.print_exc()
                            stream = None
                    if stream != None:
                        stream.start_stream()
                if commandType==Audio.PLAY:
                    # print "Play",len(commandData)
                    dataBuffer = commandData
                    bufferOffset = 0
                elif commandType==Audio.STOP:
                    # print "Stop"
                    if stream != None:
                        stream.stop_stream()
                        dataBuffer = None


