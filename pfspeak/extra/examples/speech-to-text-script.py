import time
import sounddevice

from pfspeak.core.core import SpeechToText
from pfspeak.extra.contrib.playback import typewriter, padleft


def accept(partial):
    time.sleep(8)
    return len(partial.text) > 56

if __name__ == "__main__":

    stt = SpeechToText()
    with stt.streaming() as session:
        for partial in session.partials():
            if accept(partial):
                session.finalize(partial)

    for recording in session.recordings:
        recording.normalize_timestamps()
        waveform = padleft(recording.audio)
        sounddevice.play(waveform, samplerate=recording.audio.samplerate)
        for text in typewriter(recording.tokens):
            print(text, end="", flush=True)


