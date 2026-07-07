from pfspeak import PfSpeak
from pfspeak.app import pfconfig
from pfspeak.core import Fifo


def main():
    pf = PfSpeak()

    fifo = Fifo(pfconfig.pipe_path, exists_ok=True, voice=pfconfig.voice)

    with pf.streaming(fifo) as session:
        for event in session:
            pf.play(event)


