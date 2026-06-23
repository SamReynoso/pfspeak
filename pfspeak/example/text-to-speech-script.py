import sounddevice as sd

from pfspeak import TextToSpeech
from pfspeak.common import Voices



if __name__ == "__main__":

    runtime = TextToSpeech()

    ret = runtime.speak("This is a test of pfspeak", Voices.AF_BELLA)

    sd.play(ret.waveform, samplerate=24_000)
    sd.wait()

