from enum import Enum
from typing import Any, Literal
from pathlib import Path
from pydantic import BaseModel


class HotWordBias(float, Enum):
    NONE = 0.0
    SLIGHT = 1.0
    MEDIUM = 2.0
    STRONG = 4.0
    EXTREME = 8.0


class RecognizerType(str, Enum):
    ZIPFORMER = "zipformer"


class RecognizerLanguage(str, Enum):
    ENGLISH = "en"


class AudioChannels:
    MONO = 1


class AudioParams(BaseModel):
    ...


class ListenParams(BaseModel):

    feature_dim: int = 80
    samplerate: int = 16_000
    onnx: bool = True

    hot_words: list[str] | None = None
    language: str = RecognizerLanguage.ENGLISH
    hot_words_bias: float | HotWordBias = HotWordBias.NONE

    latency: float = 0.2
    treads: int = 4

    @property
    def blocksize(self) -> int:
        return self.samplerate // 10


class SpeechParams(BaseModel):

    map_location: str = "cpu"
    device: Literal["auto", "cpu", "cuda", "mps"] = "cpu"

    disable_complex: bool = False
    allow_mps_fallback: bool = True

    vocab: Any
    n_mels: Any
    n_token: Any
    n_layer: Any
    plbert: dict
    dropout: Any
    max_dur: Any
    style_dim: Any
    istftnet: dict
    hidden_dim: Any
    text_encoder_kernel_size: Any


class G2PParams(BaseModel):
    default_lang: str = "a"
    trf: bool = False

    @staticmethod
    def infer_version_from_kokoro(kokoro_model_id):
        if kokoro_model_id.endswith('/Kokoro-82M'):
            return None
        else:
            return '1.1'
