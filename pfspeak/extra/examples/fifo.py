from pfspeak import PfSpeak
from pfspeak.core.devices import Fifo
from pfspeak.extra.voices import Voices
from pfspeak.common.dataclasses import PfEvent


DESCRIPTION = "FIFO named pipe text-to-speech example"

pf = PfSpeak()

def app(_, event: PfEvent):
    pf.play(event)


def main() -> int:
    try:

        fifo = Fifo("./input.pipe", voice=Voices.EN.AF_HEART)
        pf.run(app, fifo)

    except Exception:
        return 1
    return 0
