from __future__ import annotations
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from torch import Tensor
    from misaki.ja import Token
    from misaki.en import MToken

from pathlib import Path

from dataclasses import dataclass
from pydantic import BaseModel

from typing import Iterable, List, overload, Optional


class PipelineCmds(BaseModel):
    op: Literal["stop", "speak"]
    text: Optional[str] = None
    voice: Optional[Path] = None
    speed: Optional[float] = None
    lang: Optional[str] = None

type TokenIterable = Iterable[PfToken] | Iterable[MToken] | TokenList


@dataclass
class PfToken:
    phonemes: Optional[str]
    whitespace: str
    text: str
    start_ts: Optional[float] = None
    end_ts: Optional[float] = 0


class TokenList:

    def __init__(self, tokens: Optional[TokenIterable] = None): 
        if tokens:
            self.tokens: List[PfToken] = [
                PfToken(
                    text=t.text,
                    phonemes=t.phonemes,
                    whitespace=t.whitespace,
                    start_ts=t.start_ts,
                    ) 
                for t in tokens
                ]
        else:
            self.tokens = []
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
        return "".join([ t.text + t.whitespace for t in self.tokens ])

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
    audio: Tensor
    pred_dur: Optional[Tensor] = None


@dataclass
class Result:
    # graphemes: str
    phoneme_string: Optional[str]
    tokens: Optional[TokenList]
    audio: Optional[Tensor]
    prediction_duration: Optional[Tensor]

    def __init__(self,
                 tokens: TokenList | None = None,
                 phoneme_string: str | None = None,
                 audio: Optional[Tensor] = None,
                 prediction_duration: Optional[Tensor] = None
                 ) -> None:
        if tokens:
            self.phoneme_string = tokens.phonemes
        else:
            self.phoneme_string = phoneme_string
        self.tokens = tokens
        self.audio = audio
        self.prediction_duration = prediction_duration

    @property
    def pred_dur(self) -> Optional[Tensor]:
        return self.prediction_duration

    def join_timestamps(self):
        if self.prediction_duration is None:
            return
        assert self.pred_dur
        MAGIC_DIVISOR = 80
        if not self.tokens or len(self.pred_dur) < 3:
            return
        left = right = 2 * max(0, self.pred_dur[0].item() - 3)
        i = 1
        for t in self.tokens:
            if i >= len(self.pred_dur)-1:
                break
            if not t.phonemes:
                if t.whitespace:
                    i += 1
                    left = right + self.pred_dur[i].item()
                    right = left + self.pred_dur[i].item()
                    i += 1
                continue
            j = i + len(t.phonemes)
            if j >= len(self.pred_dur):
                break
            t.start_ts = left / MAGIC_DIVISOR
            token_dur = self.pred_dur[i: j].sum().item()
            space_dur = self.pred_dur[j].item() if t.whitespace else 0
            left = right + (2 * token_dur) + space_dur
            t.end_ts = left / MAGIC_DIVISOR
            right = left + space_dur
            i = j + (1 if t.whitespace else 0)


    def __add__(self, other: "Result") -> "Result":
        import torch
        return Result(
                phoneme_string=(
                    (self.phoneme_string or "") + (other.phoneme_string or "")
                    )
                ,
                tokens=(
                    (self.tokens or TokenList()) + (other.tokens or TokenList())
                    )
                ,
            audio=torch.cat([
                t for t in (self.audio, other.audio)
                if t is not None
            ]),
            prediction_duration=torch.cat([
                t for t in (self.prediction_duration,
                            other.prediction_duration)
                if t is not None
            ]),
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
        dur = (
                int(self.prediction_duration.sum())
                if self.prediction_duration is not None
                else None
                )

        audio_len = (
            int(self.audio.numel())
            if self.audio is not None
            else None
        )

        p_len = len(self.phoneme_string) if self.phoneme_string else 0

        return (
            f"Result("
            f"phonemes={p_len}, "
            f"dur={dur}, "
            f"audio={audio_len}"
            f")"
        )

    def __repr__(self) -> str:
        ps = self.phoneme_string
        if ps:
            if len(ps) > 40:
                ps = ps[:37] + "..."

        return (
            f"Result("
            f"phoneme_string={ps!r}, "
            f"audio_shape="
            f"{tuple(self.audio.shape) if self.audio is not None else None}, "
            f"pred_dur_shape="
            f"{
            tuple(self.prediction_duration.shape) 
            if self.prediction_duration is not None
            else None
            }"
            f")"
        )

