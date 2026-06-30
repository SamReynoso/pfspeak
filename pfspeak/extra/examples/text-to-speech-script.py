
import sounddevice as sd

from pfspeak.core.core import PfSpeak
from pfspeak.core.devices import Fifo


def start_stream():
    pf = PfSpeak()
    fifo = Fifo("./input.pipe")

    with pf.streaming(fifo) as session:
        for event in session:
            if event.recording:
                sd.play(event.recording.to_waveform(),
                        samplerate=24_000)
                sd.wait()
            print(event.status)


if __name__ == "__main__":
    start_stream()

