from pfspeak import PfSpeak
from pfspeak.core.devices import Microphone


DESCRIPTION = "Basic microphone speech-to-text example"


def main():
    pf = PfSpeak()
    microphone = Microphone()
    with pf.streaming(microphone) as session:
        for event in session:
            pf.print(event)
