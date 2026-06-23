from time import time

from pathlib import Path
from dataclasses import dataclass
from pydantic import BaseModel


from typing import Iterable, List, Optional, Any, Literal

from pfspeak.common.just_checking import TypeTensor, NDArray, Float32


class PipelineCmds(BaseModel):
    op: Literal["stop", "speak"]
    text: str
    voice: Path
    lang: Optional[str] = None
    speed: float = 1 


@dataclass
class PfToken:
    phonemes: Optional[str]
    whitespace: str
    text: str
    start_ts: Optional[float] = None
    end_ts: Optional[float] = 0


type TokenIterable = Iterable[PfToken] | TokenList

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
                ).strip()

    def __len__(self) -> int:
        return len(self.phonemes)

    def __getitem__(self, item):
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


@dataclass
class Output:
    audio: TypeTensor
    pred_dur: Optional[TypeTensor] = None


Waveform = NDArray[Float32]
WaveformBuffer = List[Waveform]

@dataclass
class Result:
    waveform: NDArray[Float32]
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
        return " ".join([t.text for t in self.tokens]).strip()

    @property
    def phonemes(self):
        return " ".join([t.phonemes for t in self.tokens if t.phonemes]).strip()

    def apply_timestamp(self, timestamp: Any = None):
        if timestamp is None:
            ct = time()
        else:
            ct = timestamp.currentTime
        for t in self.tokens:
            t.start_ts = ct

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
                tokens=(self.tokens + other.tokens)
                ,
            waveform=numpy.concatenate(
                [t for t in (self.waveform, other.waveform)]
                )
            ,
            )

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
