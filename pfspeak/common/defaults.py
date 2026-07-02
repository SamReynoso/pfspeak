from enum import StrEnum
from pathlib import Path
from dataclasses import dataclass
from platformdirs import PlatformDirs


class ModelLabels(StrEnum):
    ENGLISH_RECOGNIZER = "en-recognizer"
    KOKORO = "kokoro"
    KOKORO_V1 = "kokoro-v1"


STREAMING_MODELS = [
        ModelLabels.ENGLISH_RECOGNIZER
        ]


REMOTES = {
        ModelLabels.KOKORO:
        'hexgrad/Kokoro-82M',

        ModelLabels.KOKORO_V1:
        'hexgrad/Kokoro-82M-v1.1-zh',

        ModelLabels.ENGLISH_RECOGNIZER:
        "csukuangfj/sherpa-onnx-streaming-zipformer-en-kroko-2025-08-06",
        }

IPC_AUTHKEY = b"pfspeak"

DEFAULT_LLM = "qwen3:0.6b"

ALIASES = {
        'en-us': 'a',
        'en-gb': 'b',
        'es': 'e',
        'fr-fr': 'f',
        'hi': 'h',
        'it': 'i',
        'pt-br': 'p',
        'ja': 'j',
        'zh': 'z',
        }


LANG_CODES = dict(
        # pip install misaki[en]
        a='American English',
        b='British English'
        ,
        # espeak-ng
        e='es',
        f='fr-fr',
        h='hi',
        i='it',
        p='pt-br',

        # pip install misaki[ja]
        j='Japanese',

        # pip install misaki[zh]
        z='Mandarin Chinese',
        )


@dataclass(slots=True)
class AppSpec:
    version: str
    org_name: str
    app_name: str

    data_dir: Path
    cache_dir: Path
    config_dir: Path

    config_file: Path
    use_model_dir: bool = True

    @property
    def models_dir(self) -> Path:
        if self.use_model_dir:
            return self.data_dir / "models"
        else:
            return self.data_dir


class RepoSpec:
    model_label: ModelLabels
    model_id: str
    MANIFEST: list[str]

    @property
    def modle_id(self) -> str:
        return REMOTES[self.model_label]

    @property
    def model_dir_name(self) -> str:
        return self.model_label

    @property
    def is_a_streaming_model(self) -> bool:
        return self.model_label in STREAMING_MODELS


_org_name = "pforg" 
_app_name = "pfspeak"

_platform_dirs = PlatformDirs(appname=_app_name, appauthor=_org_name)

DEFAULT_APP_SPEC = AppSpec(
        version="handmaid",
        org_name=_org_name, 
        app_name=_app_name,

        data_dir=Path(_platform_dirs.user_data_dir),
        cache_dir=Path(_platform_dirs.user_cache_dir),
        config_dir=Path(_platform_dirs.user_config_dir),
        config_file=Path(_platform_dirs.user_config_dir) / f"{_app_name}.toml",
        )
