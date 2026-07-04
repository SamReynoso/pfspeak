from pfspeak import PfSpeak
from pfspeak.core.devices import Fifo


def basic_tts():
    pf = PfSpeak()
    fifo = Fifo("./input.pipe")

    with pf.streaming(fifo) as session:
        for event in session:
            pf.play(event)
