import wave,struct
from wave import WAVE_FORMAT_PCM

def bext(description="",originator="",
        originatorReference="",
        originationDate="",
        originationTime="",
        timeReference=0L,
        version=2,
        UMID="",
        loudnessValue=0,
        loudnessRange=0,
        maxTruePeakLevel=0,
        maxMomentaryLoudness=0,
        maxShortTermLoudness=0,
        codingHistory=""):
    size = 256+32+32+10+8+10+64+10+180+len(codingHistory)
    block = struct.pack("<4sI256s32s32s10s8sIIH64sHHHHH180s",
            "bext",size,description,originator,originatorReference,originationDate,
             originationTime,timeReference&0xFFFFFFFF,timeReference>>32,version,UMID,loudnessValue,loudnessRange,maxTruePeakLevel,
             maxMomentaryLoudness,maxShortTermLoudness,"\0"*180)
    bextblock = block+codingHistory
    return bextblock

def ixml(project="MlRawViewer",tape=1,scene=1,shot=1,take=1,angle="ms",fpsn=25000,fpsd=1000):
    blockdata = '<?xml version="1.0" encoding="UTF-8"?><BWFXML><IXML_VERSION>1.5</IXML_VERSION><PROJECT>%s</PROJECT><NOTE></NOTE><CIRCLED>FALSE</CIRCLED><BLACKMAGIC-KEYWORDS></BLACKMAGIC-KEYWORDS><TAPE>%d</TAPE><SCENE>%d</SCENE><BLACKMAGIC-SHOT>%d</BLACKMAGIC-SHOT><TAKE>%d</TAKE><BLACKMAGIC-ANGLE>%s</BLACKMAGIC-ANGLE><SPEED><MASTER_SPEED>%d/%d</MASTER_SPEED><CURRENT_SPEED>%d/%d</CURRENT_SPEED><TIMECODE_RATE>%d/%d</TIMECODE_RATE><TIMECODE_FLAG>NDF</TIMECODE_FLAG></SPEED></BWFXML>'%(project,tape,scene,shot,take,angle,fpsn,fpsd,fpsn,fpsd,fpsn,fpsd)
    #padding = 8-len(blockdata)%8
    #blockdata += ' '*padding
    block = struct.pack("<4sI","iXML",len(blockdata))+blockdata
    return block

class wavext(wave.Wave_write):
    """
    Extended version of standard python wave class
    that allows extra blocks such as the Broadcast Wave (bext) extension
    """

    def initfp(self, file):
        wave.Wave_write.initfp(self,file)
        self._blocks = ()
        self._blocklength = 0

    def setextra(self,blocks):
        """
        Provide a sequence of blocks to be inserted to the wave
        """
        self._blocks = blocks
        self._blocklength = 0
        for b in blocks:
            self._blocklength += len(b)

    def _write_header(self, initlength):
        assert not self._headerwritten
        self._file.write('RIFF')
        if not self._nframes:
            self._nframes = initlength / (self._nchannels * self._sampwidth)
        self._datalength = self._nframes * self._nchannels * self._sampwidth
        self._form_length_pos = self._file.tell()
        self._file.write(struct.pack('<L4s',36 + self._blocklength + self._datalength, 'WAVE'))
        for b in self._blocks:
            self._file.write(b)
        self._file.write(struct.pack('<4sLHHLLHH4s','fmt ', 16,
            WAVE_FORMAT_PCM, self._nchannels, self._framerate,
            self._nchannels * self._framerate * self._sampwidth,
            self._nchannels * self._sampwidth,
            self._sampwidth * 8, 'data'))
        self._data_length_pos = self._file.tell()
        self._file.write(struct.pack('<L', self._datalength))
        self._headerwritten = True

    def _patchheader(self):
        assert self._headerwritten
        if self._datawritten == self._datalength:
            return
        curpos = self._file.tell()
        self._file.seek(self._form_length_pos, 0)
        self._file.write(struct.pack('<L', 36 + self._blocklength + self._datawritten))
        self._file.seek(self._data_length_pos, 0)
        self._file.write(struct.pack('<L', self._datawritten))
        self._file.seek(curpos, 0)
        self._datalength = self._datawritten

if __name__ == '__main__':
    w = wavext("test.wav")
    w.setparams((2,2,48000,0,"NONE",""))
    w.setextra((bext(),ixml()))
    w.writeframes("".join("\0"+chr(c%128) for c in range(1000)))
    w.close()
