from typing import Generator

from pfspeak.common.dataclasses import Audio, PfToken, TokenList
from time import monotonic, sleep
from numpy import zeros, float32, concatenate


def typewriter(tokens: TokenList) -> Generator[str]:
    start = monotonic()

    for token in tokens:
        assert token.start_time
        while monotonic() - start < token.start_time:
            sleep(.005)
        yield token.text + token.whitespace


def padleft(audio: Audio):
    cursor = audio.start_time

    waveform = []
    for chunk in audio:
        dead_air = chunk.start_time - cursor 
        if dead_air > 0:
            padding = zeros(int(dead_air * chunk.samplerate), dtype=float32)
            waveform.append(padding)
        waveform.append(chunk.waveform)
        cursor = chunk.end_time

    return concatenate(waveform)
