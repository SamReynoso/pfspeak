from time import time

from pathlib import Path
from itertools import groupby
from dataclasses import dataclass
from difflib import SequenceMatcher
from dataclasses import dataclass
from pfspeak.common.just_checking import TypeTensor
from pfspeak.common.just_checking import NDArray, Float32
from typing import Iterable, List, Optional, Literal, overload, Callable, Union


type Waveform = NDArray[Float32]
type WaveformBuffer = list[Waveform]
type TokenIterable = Iterable[PfToken] | TokenList
type DifferedDef = Union[Callable, None]
type VoidableDef = Union[Callable, None]
type AudioCallback = Callable[[AudioChunk], None]


@dataclass(frozen=True)
class CudaSupport:
    available: bool
    supported: bool


@dataclass
class PipelineCmds:
    op: Literal["stop", "speak"]
    tokens: TokenList
    voice: str
    speed: float = 1 


@dataclass
class Output:
    audio: TypeTensor
    pred_dur: TypeTensor | None = None


@dataclass
class PfToken:
    phonemes: Optional[str]
    whitespace: str
    text: str
    start_ts: Optional[float] = None
    end_ts: Optional[float] = 0

    @property
    def identity(self):
        return (self.text, self.whitespace, self.phonemes or "")

    def __eq__(self, value: object, /) -> bool:
        if not isinstance(value, PfToken):
            return NotImplemented
        return self.identity == value.identity

class TokenList:

    def __init__(self, tokens: Optional[TokenIterable] = None): 
        self.tokens: List[PfToken] = []
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
                )

    def __len__(self) -> int:
        return len(self.phonemes)

    def __eq__(self, value: object, /) -> bool:
        if not isinstance(value, TokenList):
            return NotImplemented
        return list(self) == list(value)

    @property
    def count(self):
        return len(self.tokens)

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

    def append(self, token):
        self._phonemes = None
        self._text = None
        self.tokens.append(token)

    def revise(self, new: TokenList) -> TokenList:
        old_text = [t.identity for t in self]
        new_text = [t.identity for t in new]

        matcher = SequenceMatcher(a=old_text, b=new_text)
        merged = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            match tag:
                case "equal":
                    merged.extend(self[i1:i2])
                case "replace":
                    merged.extend(new[j1:j2])

                case "insert":
                    merged.extend(new[j1:j2])

                case "delete":
                    pass
        self.tokens = merged
        return self

@dataclass
class AudioChunk:
    waveform: Waveform
    samplerate: int
    start_time: float

    @property
    def duration(self) -> float:
        return self.waveform.shape[0] / self.samplerate

    @property
    def end_time(self) -> float:
        return self.start_time + self.duration


class Audio(list[AudioChunk]):

    @property
    def start_time(self):
        if not self:
            raise RuntimeError("Empty Audio has no start time")
        return self[0].start_time

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

        return self[-1].end_time - self[0].start_time


class Recording:
    @property
    def waveform(self):
        ...

    @property
    def text(self) -> str:
        return self.tokens.text

    def replay(self):
        i = 0
        for token_index, group in groupby(self.ledger):
            n = sum(1 for _ in group)
            yield self.tokens[token_index], self.audio[i:i+n]
            i += n

    def __init__(self,
                 tokens: TokenList | None = None,
                 audio: Audio | None = None,
                 ) -> None:
        self.tokens: TokenList = tokens or TokenList()
        self.audio: Audio = audio or Audio()
        self.ledger: list[int] = []

    def revise(self, tokens: TokenList, audio: Audio):
        self.tokens.revise(tokens)
        self.audio += audio
        self.apply_timestamp(audio)

    def concatenate(self):
        import numpy
        return numpy.concatenate([c.waveform for c in self.audio])

    @staticmethod
    def float_list(start: float, end: float, count: int):
        if count <= 2:
            return [start, end]
        step = (end - start) / (count - 1)
        return [start + i * step for i in range(count)]


    def apply_timestamp(self, audio: Audio):

        pending = [t for t in self.tokens if t.start_ts is None]
        if not pending:
            return
        start = audio[0].start_time
        end = audio[-1].end_time
        times = self.float_list(start, end, self.tokens.count + 1,)

        for token, start_ts, end_ts in zip(pending, times, times[1:]):
            token.start_ts = start_ts
            token.end_ts = end_ts

        first_pending = self.tokens.count - len(pending)

        self.ledger.extend(
                first_pending + min(
                    (i * len(pending)) // len(audio),
                    len(pending) - 1,
                    )
                for i in range(len(audio))
                )

    def normalize_timestamps(self):
        if not self.tokens:
            return
        start = self.tokens[0].start_ts
        assert start
        for token in self.tokens:
            if token.start_ts is None or token.end_ts is None:
                raise RuntimeError("Can not normalize token with null timestamps")
            token.start_ts -= start
            token.end_ts -= start




@dataclass
class Result:
    waveforms: NDArray[Float32]
    tokens: TokenList

    def __init__(self,
                 waveform: Waveform | WaveformBuffer,
                 tokens: TokenList
                 ) -> None:

        self.tokens = tokens
        if isinstance(waveform, list):
            import numpy
            self.waveform = numpy.concatenate(waveform)
        else:
            self.waveform = waveform

    @property
    def text(self):
        return self.tokens.text

    @property
    def len(self):
        return len(self.text)

    @property
    def age(self):
        if (end := self.tokens[-1].end_ts):
            return time() - end
        raise NotImplementedError

    @property
    def phonemes(self):
        return self.tokens.phonemes


    def join_timestamps(self, prediction_duration):
        if prediction_duration is None:
            return
        MAGIC_DIVISOR = 80
        if not self.tokens or len(prediction_duration) < 3:
            return
        left = right = 2 * max(0, prediction_duration[0].item() - 3)
        i = 1
        for t in self.tokens:
            if i >= len(prediction_duration)-1:
                break
            if not t.phonemes:
                if t.whitespace:
                    i += 1
                    left = right + prediction_duration[i].item()
                    right = left + prediction_duration[i].item()
                    i += 1
                continue
            j = i + len(t.phonemes)
            if j >= len(prediction_duration):
                break
            t.start_ts = left / MAGIC_DIVISOR
            token_dur = prediction_duration[i: j].sum().item()
            space_dur = prediction_duration[j].item() if t.whitespace else 0
            left = right + (2 * token_dur) + space_dur
            t.end_ts = left / MAGIC_DIVISOR
            right = left + space_dur
            i = j + (1 if t.whitespace else 0)

    def __add__(self, other: Result) -> Result:
        import numpy
        return Result(
                tokens=(self.tokens + other.tokens),
                waveform=numpy.concatenate([self.waveform, other.waveform]),
                )

    def __eq__(self, value: object, /) -> bool:
        if isinstance(value, str):
            return (
                    self.text.casefold() == value.casefold
                    or
                    self.phonemes.casefold() == value.casefold()
                    )
        elif isinstance(value, Result):
            return self.tokens == value.tokens

        return NotImplemented

    @classmethod
    def join(cls, results: Iterable[Result]) -> Result:
        results = list(results)
        if not results:
            raise ValueError("Cannot join empty results")
        out = results[0]
        for r in results[1:]:
            out += r
        return out

    def __str__(self) -> str:
        return (
            f"Result("
            f"waveform={len(self.waveform)}, "
            f"text={len(self.text)}, "
            f"phonemes={len(self.phonemes)}, "
            f")"
        )

    def __repr__(self) -> str:
        ps = self.phonemes
        if len(ps) > 40:
            ps = ps[:37] + "..."

        txt = self.text
        if len(txt) > 40:
            txt = txt[:37] + "..."

        return (
            f"Result("
            f"phoneme_string={ps!r}, "
            f"waveform_shape=,{txt!r}, "
            f"{tuple(self.waveform.shape)}, "
            f")"
        )
