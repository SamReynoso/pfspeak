import time

import sounddevice as sd

from pfspeak import TextToSpeech
from pfspeak.common import Voices



if __name__ == "__main__":

    tts = TextToSpeech()

    with tts.streaming() as session:
        for ret in session.read("This is a test for pfspeak", Voices.AF_HEART):
            time.sleep(10)
            print("sleeping", ret)
            sd.play(ret.waveform, samplerate=24_000)
            sd.wait()

