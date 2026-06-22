import time
start = time.time()
#import sounddevice as sd

from pfspeak.tts.runtime import Runtime, Voices


runtime = Runtime()


if __name__ == "__main__":

    #
    # pip install sounddevice
    #

    ret = runtime.speak("This is a test of pfspeak", Voices.AF_BELLA)

    # sd.play(ret.audio, samplerate=24_000)
    # sd.wait()
    print(time.time() - start)

