from enum import Enum
from typing import List
from pfspeak.common.defaults import  RuntimeSpec
from pfspeak.common import MODEL_NAMES


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


class RecognizerSpec(RuntimeSpec):
    samplerate: int
    feature_dim: int

    hot_words: List[str] | None = None
    hot_words_bias: float | HotWordBias = HotWordBias.NONE
    treads: int = 4
    onnx: bool = True
    language: str = RecognizerLanguage.ENGLISH
    samplerate: int

    is_a_streaming_model: bool


    @property
    def blocksize(self) -> int:
        # About 100ms latency
        return self.samplerate // 10


class KrokoRecognizerSpec(RecognizerSpec, RuntimeSpec):
    model_label: str | None =  'sherpa-zipformer'
    model_id: str = MODEL_NAMES['sherpa-zipformer']
    model_type: str = RecognizerType.ZIPFORMER

    samplerate: int = 16_000
    feature_dim: int = 80
    latency: float = 0.2

    language: str = RecognizerLanguage.ENGLISH
    is_a_streaming_model: bool = True
    onnx: bool = True



