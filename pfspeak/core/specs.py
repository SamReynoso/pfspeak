from pathlib import Path
from typing import Literal, Optional, Any, Dict
from pydantic import BaseModel


class ModelSpec(BaseModel):
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
    weights_only: bool = True
    device: str = "cpu"

    model_path: Path


class AppSpec(BaseModel):
    version: str
    org_name: str
    app_name: str

    data_dir: Path
    cache_dir: Path
    config_dir: Path

    config_file: Path


class RuntimeSpec(BaseModel):
    name: str = "default"

    data_root: Path = Path("./data")
    cache_root: Path = Path("./cache")
    voice_root: Optional[Path] = None
    config_path: Optional[Path] = None
    model_path: Optional[Path] = None

    model_source: Literal[
            "local",
            "huggingface",
            ] = "huggingface"
    model_id: str = "hexgrad/Kokoro-82M"
    voice_source: Literal[
            "local",
            "huggingface",
            ] = "huggingface"
    token: Optional[str] = None
    discover_token: bool = True
    env_token_name: Optional[str] = None

    use_provider_config: bool = True
    local_only: bool = False
    preload: bool = True
    lazy_load: bool = False
    verify: bool = True
    raise_for_errors: bool = True
    offline: bool = False
    auto_download: bool = True

    device: Literal[
            "auto",
            "cpu",
            "cuda",
            "mps",
            ] = "auto"

    allow_mps_fallback: bool = True
    default_lang: str = "a"
    trf: bool = False
    default_speed: float = 1.0
    kokoro_version: Optional[str] = None

    disable_complex: bool = False
    map_location: str = "cpu"
    weights_only: bool = True


    def __init__(self, /, **data: Any) -> None:
        super().__init__(**data)
        if self.model_id.endswith('/Kokoro-82M'):
            self.kokoro_version = None
        else:
            self.kokoro_version = '1.1'


