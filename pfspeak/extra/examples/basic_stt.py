from pfspeak import PfSpeak
from pfspeak.core.devices import Microphone


def basic_stt():
    pf = PfSpeak()
    microphone = Microphone()
    with pf.streaming(microphone) as session:
        for event in session:
            pf.print(event)
