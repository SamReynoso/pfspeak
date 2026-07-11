from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pfspeak.core.devices import InputStream

from uuid import UUID
from enum import StrEnum
from difflib import SequenceMatcher
from time  import time, monotonic_ns
from typing import Iterable, overload
from dataclasses import dataclass, field
from pfspeak.extra.voices import VoiceEnum
from pfspeak.common.just_checking import NDArray, Float32, TypeTensor


@dataclass(slots=True)
class PfEvent:

    class EventTypes(StrEnum):
        TEXT = "text"
        TTS = "tts"
        STT = "stt"
        DUCK = "duck"
        TICKET = "ticket"

    service: EventTypes
    device_id: UUID | None

    device: InputStream | None
    request: WorkRequest | None
    recording: Recording | None

    finalized: bool
    _status: str = ""

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, value):
        self._status = str(value)

    @property
    def types(self):
        return self.EventTypes

    def __repr__(self):
        return (f"PfEvent(service={self.service}, "
                f"recording={len(self.recording.text) if self.recording else 0}"
                ")")

    @property
    def duration(self):
        if not self.recording:
            raise ValueError("Event recording is None")
        return self.recording.audio.duration

    @property
    def start_time(self):
        if not self.recording:
            raise ValueError("Event recording is None")
        return self.recording.audio.start_time

    @property
    def end_time(self):
        if not self.recording:
            raise ValueError("Event recording is None")
        return self.recording.audio.end_time

    @property
    def text(self):
        if not self.recording and not self.request:
            raise ValueError("Event missing text content")
        if self.recording:
            return self.recording.text
        assert self.request
        return self.request.tokens.text

    @classmethod
    def as_ticket(cls):
        return cls(device=None,
                   device_id=None,
                   recording=None,
                   finalized=True,
                   request=None,
                   service=PfEvent.EventTypes.TICKET)



@dataclass(slots=True)
class WorkRequest:
    device_id: UUID
    tokens: TokenList
    voice: VoiceEnum | str
    speed: float = 1 

    def __repr__(self) -> str:
        voice = f"'{self.voice}'" if self.voice else None
        return ("WorkerRequest(, "
                f"tokens={len(self.tokens)}, "
                f"voice={voice}, "
                f"speed={self.speed})"
                )

    def make(self,
             tokens: TokenList,
             voice: VoiceEnum | str | None = None,
             *,
             speed: float | None = None
             ) -> WorkerMessage:
        if voice is None:
            if self.voice is None:
                raise ValueError("No voice proviced in WorkRequest")
            voice = self.voice
        if speed is None:
            speed = self.speed
        return WorkerMessage(
                device_id=self.device_id,
                op="speak",
                tokens=tokens,
                voice=voice,
                speed=speed)


class Recording:

    def __init__(self,
                 tokens: TokenList | None = None,
                 audio: Audio | None = None,
                 *,
                 ledger: list[int] | None = None,
                 ) -> None:
        self.tokens: TokenList = tokens or TokenList()
        self.audio: Audio = audio or Audio()
        self.ledger = ledger or  []
        self.apply_timestamp()
        self.bump_revision_number()

    @property
    def text(self):
        return self.tokens.text

    @property
    def phonemes(self):
        return self.tokens.phonemes

    def to_waveform(self):
        return self.audio.to_waveform()

    def revise(self, tokens: TokenList, audio: Audio):
        self.bump_revision_number()
        self.revise_tokens(tokens)
        self.audio += audio
        self.apply_timestamp()

    def bump_revision_number(self):
        for token in self.tokens:
            if token.revision is not None:
                token.revision += 1
            else:
                token.revision = 0

    def apply_timestamp(self):

        new_audio = self.audio[len(self.ledger):]

        pending = [t for t in self.tokens if t.start_time is None]
        if not pending:
            return
        if not new_audio:
            raise RuntimeError("Some tokens are missing timestamps")
        start = new_audio[0].start_time
        end = new_audio[-1].end_time
        times = float_range(start, end, self.tokens.count + 1,)

        for token, start_ts, end_ts in zip(pending, times, times[1:]):
            token.start_time = start_ts
            token.end_time = end_ts

        first_pending = self.tokens.count - len(pending)

        self.ledger.extend(
                first_pending + min(
                    (i * len(pending)) // len(new_audio),
                    len(pending) - 1,
                    )
                for i in range(len(new_audio))
                )

    def normalize_timestamps(self):
        if not self.tokens:
            return
        start = self.tokens[0].start_time
        assert start
        for token in self.tokens:
            if token.start_time is None or token.end_time is None:
                raise RuntimeError(
                        "Can not normalize token with null timestamps"
                        )
            token.start_time -= start
            token.end_time -= start

    def revise_tokens(self, new: TokenList) -> None:
        old_id = [t.identity for t in self.tokens]
        new_id = [t.identity for t in new]

        matcher = SequenceMatcher(a=old_id, b=new_id)
        merged = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            match tag:
                case "equal":
                    merged.extend(self.tokens[i1:i2])
                case "replace":
                    merged.extend(new[j1:j2])
                case "insert":
                    merged.extend(new[j1:j2])
                case "delete":
                    pass
        self.tokens = TokenList(merged)

    def head(self, index: int):
        audio = Audio(
                [self.audio[i] for i, t in enumerate(self.ledger) if t < index]
                )
        return Recording(
                tokens=self.tokens[:index],
                ledger=self.ledger[:index],
                audio=audio)

    def tail(self, index: int):
        audio = Audio(
                [self.audio[i] for i, t in enumerate(self.ledger) if t >= index]
                )
        return Recording(
                tokens=self.tokens[index:],
                ledger=self.ledger[index:],
                audio=audio)

    def __add__(self, other: Recording) -> Recording:
        return Recording(
                tokens=self.tokens + other.tokens,
                audio=self.audio + other.audio,
                ledger=self.ledger + other.ledger,
                )

    def __eq__(self, value: object, /) -> bool:
        if isinstance(value, str):
            return (
                    self.text.casefold() == value.casefold
                    or
                    self.phonemes.casefold() == value.casefold()
                    )
        elif isinstance(value, Recording):
            return self.tokens == value.tokens

        return NotImplemented

    @classmethod
    def join(cls, recordings: Iterable[Recording]) -> Recording:
        recordings = list(recordings)
        if not recordings:
            raise ValueError("Cannot join empty recordings iterable")
        out = recordings[0]
        for r in recordings[1:]:
            out += r
        return out

    def __repr__(self) -> str:
        return (
            f"Recording("
            f"duration={self.audio.duration if self.audio else 'empty'}, "
            f"text={len(self.text)}, "
            f"phonemes={len(self.phonemes)}"
            f")"
        )

@dataclass(slots=True)
class PfToken:
    phonemes: str | None
    whitespace: str
    text: str
    start_time: float | None = None
    end_time: float | None = None
    revision: int | None = None
    _len: int | None = None

    @property
    def identity(self):
        return (self.text, self.whitespace, self.phonemes or "")

    def __eq__(self, value: object, /) -> bool:
        if not isinstance(value, PfToken):
            return NotImplemented
        return self.identity == value.identity

    def __len__(self):
        """
        Return the phoneme length of this token.

        `len(PfToken)` and `len(TokenList)` measure phoneme length rather
        than token count.
        """
        if self._len is not None:
            return self._len
        ps_len = len(self.phonemes) if self.phonemes else 0
        self._len = ps_len + len(self.whitespace)
        return self._len

    def __repr__(self) -> str:
        text = self.text
        if len(self.text) > 35:
            text = text[:32] + "..."

        return (
                f"PfToken(len={len(self)}, "
                f"text='{text}', "
                f"start_time={self.start_time}, "
                f"{self.revision})"
                )


class TokenList:

    def __init__(self, tokens: Iterable[PfToken] | None = None): 
        self.tokens: list[PfToken] = []
        if tokens:
            self.tokens =  list(tokens)
        self._phonemes = None
        self._text = None

    @property
    def phonemes(self):
        if self._phonemes:
            return self._phonemes
        return "".join(
                [
                    t.phonemes + (" " if t.whitespace else "")
                    for t in self.tokens  if t.phonemes 
                    ]
                ).strip()

    @property
    def text(self):
        return "".join(
                [
                    t.text + (" " if t.whitespace else "")
                    for t in self.tokens if t.phonemes
                    ]
                ).strip()

    @property
    def count(self):
        return len(self.tokens)

    def append(self, token):
        self._phonemes = None
        self._text = None
        self.tokens.append(token)

    def __eq__(self, value: object, /) -> bool:
        if not isinstance(value, TokenList):
            return NotImplemented
        return list(self) == list(value)

    def __len__(self) -> int:
        """
        RETURN THE TOTAL PHONEME LENGTH, NOT THE NUMBER OF TOKENS.

        This makes phoneme-budgeted algorithms read naturally.

            while len(tokens[:i]) < max_size:
                i += 1

        Use `count` to get the number of `PfToken` objects.
        """
        return len(self.phonemes)

    @overload
    def __getitem__(self, item: int) -> PfToken: ...

    @overload
    def __getitem__(self, item: slice) -> TokenList: ...

    def __getitem__(self, item: int | slice):
        if isinstance(item, slice):
            return TokenList(self.tokens[item])
        return self.tokens[item]

    def __iter__(self):
        for item in self.tokens:
            yield item

    def __add__(self, other: TokenList) -> TokenList:
        return TokenList(self.tokens + other.tokens)

    def __repr__(self) -> str:
        text = self.text
        if len(text) > 35:
            text = text[:32] + "..."
        return f"TokenList(len={len(self)}, count={self.count}, text='{text}')"


@dataclass(slots=True)
class AudioChunk:
    device_id: UUID
    waveform: NDArray[Float32]
    samplerate: int
    start_time: float = field(default_factory=time)
    created_ns: int = field(default_factory=monotonic_ns)

    _rms: float | None = None
    _peak: float | None = None


    @property
    def rms(self):
        import numpy
        if self._rms is None:
            self._rms = numpy.sqrt(numpy.mean(self.waveform**2))
        return self._rms

    @property
    def peak(self):
        import numpy
        if self._peak is None:
            self._peak = numpy.max(numpy.abs(self.waveform))
        return self._peak

    @property
    def duration(self) -> float:
        return self.waveform.shape[0] / self.samplerate

    @property
    def end_time(self) -> float:
        return self.start_time + self.duration

    @property
    def modified(self) -> float:
        return self.created_ns + int(self.duration * 1e+9)

    def __repr__(self) -> str:
        return (f"AudioChunk(start_time={self.start_time}, "
                f"duration={self.duration})")

    def resample(self, samplerate: int):
        import soxr
        waveform = soxr.resample(
                self.waveform,
                in_rate=self.samplerate,
                out_rate=samplerate)

        return AudioChunk(
                device_id=self.device_id,
                waveform=waveform,
                samplerate=samplerate,
                start_time=self.start_time,
                created_ns=self.created_ns)


class Audio(list[AudioChunk]):

    def to_waveform(self):
        import numpy
        return numpy.concatenate([c.waveform for c in self])

    @property
    def created_ns(self):
        if not self:
            raise RuntimeError("Empty Audio has no start time")
        return self[0].created_ns


    @property
    def start_time(self):
        if not self:
            raise RuntimeError("Empty Audio has no start time")
        return self[0].start_time

    @property
    def end_time(self):
        if not self:
            raise RuntimeError("Empty Audio has no start time")
        return self[-1].end_time

    @property
    def samplerate(self):
        if not self:
            raise RuntimeError("Empty Audio has no samplerate")
        return self[0].samplerate

    @property
    def duration(self) -> float:
        """Total audio duration, ignoring gaps."""
        if not self:
            raise RuntimeError("Empty Audio has no duration")

        samples = sum(len(chunk.waveform) for chunk in self)
        return samples / self.samplerate

    @property
    def elapsed(self) -> float:
        """Elapsed time covered by this audio, including gaps."""
        if not self:
            raise RuntimeError("Empty Audio has no elapsed time")

        return self.end_time - self.start_time

    @property
    def modified(self):
        return self[-1].modified

    def __add__(self, other: Audio | list) -> Audio:
        _list = super().__add__(other)
        return Audio(_list)



def float_range(start: float, end: float, count: int):
    if count <= 2:
        return [start, end]
    step = (end - start) / (count - 1)
    return [start + i * step for i in range(count)]


@dataclass(slots=True)
class PfStatus:
    name: str = "Status"
    sent: int = 0
    received: int = 0
    line: str = ""
    lines: list[str] = field(default_factory=list)

    def add(self, line: str):
        self.lines.append(line)


@dataclass(frozen=True)
class CudaSupport:
    available: bool
    supported: bool


@dataclass(order=True)
class Playback:
    priority: int
    sequence: int

    waveform: NDArray[Float32] = field(compare=False)
    samplerate: int = field(compare=False)
    cursor: int = field(default=0, compare=False)


@dataclass(slots=True)
class Prediction:
    device_id: UUID
    tokens: TokenList
    audio: TypeTensor
    pred_dur: TypeTensor

    def as_event(self) -> PfEvent:
        return PfEvent(
                device=None,
                finalized=True,
                device_id=self.device_id,
                service=PfEvent.EventTypes.TTS,
                recording=Prediction.recording(self),
                request=None,
                )

    @staticmethod
    def recording(prediction):
        # TODO: ...
        from numpy import array, float32
        waveform = array(prediction.audio).astype(float32)
        chunk = AudioChunk(device_id=prediction.device_id,
                           waveform=waveform,
                           samplerate=24_000,
                           start_time=0)
        return Recording(tokens=prediction.tokens, audio=Audio([chunk])) 



class Sentinel: ...
