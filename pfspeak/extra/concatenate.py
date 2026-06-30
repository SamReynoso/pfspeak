from typing import Any
from itertools import groupby
from functools import singledispatch
from numpy import concatenate as npcat
from pfspeak.common.dataclasses import Audio, AudioChunk, Recording


@singledispatch
def concatenate(obj, *, dim: int = 0) -> Any:
    raise TypeError(f"Can't concatenate {type(obj)!r}")


@concatenate.register
def _(audio: Audio, *, dim: int = 0):
    match dim:
        case 0:
            return npcat([a.waveform for a in audio])
        case _:
            raise ValueError(f"Unsupported dim={dim}")
            ...


@concatenate.register
def _(recording: Recording, *, dim: int = 0):
    first = recording.audio[0]
    match dim:
        case 0:
            return Recording(
                    tokens=recording.tokens,
                    audio=Audio(
                        [
                            AudioChunk(
                                start_time=first.start_time,
                                samplerate=first.samplerate,
                                waveform=npcat(
                                    [
                                        c.waveform for c in recording.audio
                                        ]
                                    ),
                                )
                            ]
                        )
                    )
        case 1:
            audio = Audio()
            i = 0
            for _, group in groupby(recording.ledger):
                n = sum(1 for _ in group)
                audio.append(
                        AudioChunk(
                            start_time=recording.audio[i].start_time,
                            samplerate=first.samplerate,
                            waveform=npcat(
                                [c.waveform for c in recording.audio[n:n+1]]
                                )
                            )
                        )
                i += n
            return Recording(
                    tokens=recording.tokens,
                    audio=audio,
                    )
        case _:
            raise ValueError(f"Unsupported dim={dim}")


@concatenate.register
def _(items: list, *, dim: int = 0):
    if not items:
        raise ValueError("Empty list")

    first = items[0]

    if isinstance(first, Recording):
        return _concat_recordings(items, dim)

    if isinstance(first, Audio):
        return _concat_audios(items, dim)

    raise TypeError(type(first))


def _concat_recordings(recordings: list[Recording], dim: int):
    '''
    list[recording(tokens, list[chunks])
    recording(tokens, list[chunk])
    '''
    audio = _concat_audios([r.audio for r in recordings], dim)

    if len(recordings) > 1:
        base = recordings[0]
        for r in recordings[1:]:
            base.revise(r.tokens, r.audio)
    else:
        base = recordings[0]
    if dim == 2:
        assert isinstance(audio, Audio)
        return Recording(tokens=base.tokens, audio=audio)

    if dim == 1:
        ...
    if dim == 0:
        assert not isinstance(audio, Audio)
        return Recording(tokens=base.tokens, audio=Audio([audio]))
    raise RuntimeError(f"Dim level unsupported: {dim}")
    

def _concat_audios(audios: list[Audio], dim: int) -> Audio | AudioChunk:
    first = audios[0][0]
    kwarg = {"start_time": first.start_time, "samplerate": first.samplerate}

    base = []
    for a in audios:
        base += a

    if dim == 1:
        return Audio(base)
    if dim == 0:
        return AudioChunk(waveform=npcat([c.waveform for c in base]), **kwarg)
    raise RuntimeError(f"Dim level unsupported: {dim}")
