import numpy as np
import math,wave,sys

def FindStartTone(sampleData,sampleFrequency,channels,width,toneFrequency,toneDuration,maxdur=60.0):
    #print "Searching for tone freq %f dur %f in samples %d"%(toneFrequency,toneDuration,sampleData.shape[0])
    # Return a list of candidates for the tone position in the given sameple data
    ms = sampleFrequency*maxdur
    sw = width
    ch = channels 
    nf = len(sampleData)/(width*channels)
    if sw==2:
        wa = np.fromstring(sampleData,dtype=np.int16)
        wa = wa.reshape(-1,ch)
    elif sw == 3:
        a = np.empty((nf,ch,4),dtype=np.uint8)
        raw = np.fromstring(sampleData,dtype=np.uint8)
        a[:,:,:sw] = raw.reshape(-1,ch,sw)
        a[:,:,sw:] = (a[:,:,sw-1:sw]>>7)*255
        wa = a.view('<i4').reshape(a.shape[:-1])
    wa = wa[:,0] # Only use 1 channel

    if wa.shape[0]>ms:
        wa = wa[:ms]

    isf = 1.0/float(sampleFrequency) 
    itf = 1.0/float(toneFrequency)
    toneSamples = itf/isf # Number of samples for 1 wavelength of the tone
    # Generate a sin and cos wave at the tone frequency matching the supplied data
    phaseBase = np.arange(wa.shape[0],dtype=np.float64)
    tonePhaseDiff = math.pi*2.0/toneSamples
    phase = phaseBase * tonePhaseDiff
    s = np.sin(phase)
    c = np.cos(phase)
    ans = wa*s
    anc = wa*c
    cmans = np.cumsum(ans)
    cmanc = np.cumsum(anc)
    mag = cmans*cmans+cmanc*cmanc
    window = int(toneSamples*256) # 8 waves long accumulation
    rolling = mag[window:]-mag[:-window]
    cmroll = np.cumsum(rolling)
    lpfcr = cmroll[1000:]-cmroll[:-1000]
    am = lpfcr.argmax()
    return am,math.sqrt(lpfcr[am])

def generateTestData(sampleRate=48000.0,dur=10.0,toneLength=0.08,toneFreq=12000.0,toneOffset=2.467,toneAmp=256.0,phaseOff=0.39,noiseAmp=1024):
    # Test
    sf = float(sampleRate)
    tl = float(toneLength)
    ttf = float(toneFreq)
    dur = float(dur)
    to = float(toneOffset) 
    tamp = float(toneAmp)
    phaseoff = float(phaseOff)
    namp = float(noiseAmp)

    shape = (int(sf*dur),)
    test = np.zeros(shape=shape,dtype=np.int16)
    testnoise = ((np.random.random(test.shape)*2.0-1.0)*namp).astype(np.int16)
    testtonephase = (np.arange(0,int(tl*sf),dtype=np.float32)+phaseoff)*(math.pi*2.0*(ttf/sf))
    testtone = tamp*np.sin(testtonephase)
    test += testnoise
    test[int(to*sf):int(to*sf)+testtone.shape[0]] += testtone
    return test

def writeWav(data,sf,name):
    wav = wave.open(name,'wb')
    wav.setparams((1,2,int(sf),data.shape[0],"NONE",""))
    wav.writeframes(data.tostring())
    wav.close()    

if __name__ == '__main__':
    if len(sys.argv[1])>0:
        wavfilename = sys.argv[1]
        wav = wave.open(wavfilename,'rb')
        sf = wav.getframerate()
        nf = wav.getnframes()
        sw = wav.getsampwidth()
        ch = wav.getnchannels()
        raw = wav.readframes(nf)
        test = raw
        tf = 12000.0
        tl = 0.08
    else:
        sf = 48000.0
        tf = 12000.0
        tl = 0.08
        ch = 1
        sw = 2
        test = generateTestData(sampleRate=sf,toneFreq=tf,toneLength=tl,noiseAmp=256)
        writeWav(test,sf,"test.wav")
        test = test.tostring()

    sample = FindStartTone(test,sf,ch,sw,tf,tl)
    print sample




