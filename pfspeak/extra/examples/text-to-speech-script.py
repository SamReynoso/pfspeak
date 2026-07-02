
import sounddevice as sd

from pfspeak.core.core import PfSpeak
from pfspeak.core.devices import Fifo

def fw(text: str):
    los = 0
    for word in text.split():
        if los >= 60: los = 0
        if los == 0: sys.stdout.write("\n\t")
        sys.stdout.write(f"{word} ")
        los += len(word) + 1
    sys.stdout.flush()


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

