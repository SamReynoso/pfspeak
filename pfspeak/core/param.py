from enum import Enum
from dataclasses import dataclass
from typing import Any, Literal


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


class AudioChannels(int, Enum):
    MONO = 1


class AudioParams: ...


@dataclass(slots=True)
class ListenParams:

    treads: int = 4
    onnx: bool = True
    latency: float = 0.2
    feature_dim: int = 80
    samplerate: int = 16_000
    hot_words: list[str] | None = None
    language: str = RecognizerLanguage.ENGLISH
    hot_words_bias: float | HotWordBias = HotWordBias.NONE

    @property
    def blocksize(self) -> int:
        return self.samplerate // 10


@dataclass(slots=True)
class SpeechParams:

    vocab: Any
    n_mels: Any
    dim_in: Any  # ---
    max_conv_dim: Any  # ---
    multispeaker: Any  # ---
    n_token: Any
    n_layer: Any
    plbert: dict
    dropout: Any
    max_dur: Any
    style_dim: Any
    istftnet: dict
    hidden_dim: Any
    text_encoder_kernel_size: Any

    map_location: str = "cpu"
    disable_complex: bool = False
    allow_mps_fallback: bool = True
    device: Literal["auto", "cpu", "cuda", "mps"] = "cpu"


@dataclass(slots=True)
class G2PParams:
    trf: bool = False
    default_lang: str = "a"

    @staticmethod
    def infer_version_from_kokoro(kokoro_model_id):
        if kokoro_model_id.endswith('/Kokoro-82M'):
            return None
        else:
            return '1.1'
