from pathlib import Path
from enum import Enum
from typing import List
from pydantic import BaseModel 

from sherpa_onnx import OnlineRecognizer


class HotWordBias(float, Enum):
    NONE = 0.0
    SLIGHT = 1.0
    MEDIUM = 2.0
    STRONG = 4.0
    EXTREME = 8.0


class ModelType(str, Enum):
    ZIPFORMER = "zipformer"


class Language(str, Enum):
    ENGLISH = "en"


class Channels:
    MONO = 1


class RecognizerSpec(BaseModel):
    model_directory: str
    data_dir: Path
    samplerate: int
    feature_dim: int

    hot_words: List[str] | None = None
    hot_words_bias: float | HotWordBias = HotWordBias.NONE
    treads: int = 4
    onnx: bool = True
    language: str = Language.ENGLISH
    samplerate: int

    is_a_streaming_model: bool

    @property
    def blocksize(self) -> int:
        # About 100ms latency
        return self.samplerate // 10

    @property
    def postfix(self) -> str:
        if self.onnx:
            return ".onnx"
        return ""

    @property
    def tokens(self) -> str:
        return str(self.data_dir / self.model_directory/  "tokens.txt")

    def with_postfix(self, filename: str) -> str:
        return str(self.data_dir /self.model_directory / (filename + self.postfix))

    @property
    def encoder(self) -> str:
        return  self.with_postfix("encoder")

    @property
    def decoder(self) -> str:
        return self.with_postfix("decoder")

    @property
    def joiner(self) -> str:
        return self.with_postfix("joiner")

    def to_recognizer(self) -> OnlineRecognizer:

        if not self.data_dir.exists():
            raise RuntimeError("Could not find model in data root directory")

        if not self.is_a_streaming_model:
            raise RuntimeError("Don't forget to get the streaming model.")

        kwargs = dict()
        if self.hot_words:
            kwargs["decoding_method"] = "modified_beam_search"
            kwargs["hotwords_score"] = float(self.hot_words_bias)
            kwargs["hot_words"] = " ".join(self.hot_words)

        return OnlineRecognizer.from_transducer(
            tokens=self.tokens,
            encoder=self.encoder,
            decoder=self.decoder,
            joiner=self.joiner,
            num_threads=self.treads,
            sample_rate=self.samplerate,
            feature_dim=self.feature_dim,
            **kwargs,
        )
