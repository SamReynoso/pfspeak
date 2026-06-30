
import sounddevice as sd

from pfspeak import TextToSpeech
from pfspeak.core.sources import Fifo



def start_stream():
    tts = TextToSpeech()
    fifo = Fifo("./text.pipe")

    with tts.streaming(fifo) as session:
        for event in session.new():
            if event.recording:
                sd.play(event.recording.to_waveform(),
                        samplerate=24_000)
                sd.wait()
            print(event.status)


if __name__ == "__main__":
    start_stream()

