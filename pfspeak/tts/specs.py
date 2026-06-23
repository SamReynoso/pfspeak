from pathlib import Path

from pfspeak.common.defaults import RuntimeSpec

from pydantic import BaseModel
from typing import Literal, Optional, Any, Dict


class SpeechSpec(RuntimeSpec):
    model_id: str = "hexgrad/Kokoro-82M"
    model_label: str | None = "kokoro"

    source_params_filename: str = "config.json"
    params_filename: str = "model_params.json"


class ModelParams(BaseModel):
    vocab: Any
    style_dim: Any
    n_layer: Any
    hidden_dim: Any
    n_token: Any
    plbert: Dict
    dropout: Any
    max_dur: Any
    text_encoder_kernel_size: Any
    n_mels: Any
    istftnet: Dict

    disable_complex: bool = False
    map_location: str = "cpu"
    allow_mps_fallback: bool = True
    weights_only: bool = True
    device: Literal[
            "auto",
            "cpu",
            "cuda",
            "mps",
            ] = "auto"
    weights_file: Path


class G2PSpec(BaseModel):
    default_lang: str = "a"
    trf: bool = False
    version: Optional[str] = None

    @staticmethod
    def infer_version_from_kokoro(kokoro_model_id):
        if kokoro_model_id.endswith('/Kokoro-82M'):
            return None
        else:
            return '1.1'

    @classmethod
    def from_kokoro_model_id(cls, /, kokoro_model_id, **data: Any):
        version = cls.infer_version_from_kokoro(kokoro_model_id)
        return cls(version=version, **data)
