from enum import StrEnum
from pathlib import Path

from platformdirs import PlatformDirs
from pydantic import BaseModel

from pfspeak.core.params import RecognizerType

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


class Voices(StrEnum):
    AF_HEART = "af_heart"
    BR_LILYA = "bf_lily.pt"


class AppSpec(BaseModel):
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



class RepoSpec(BaseModel):
    model_label: ModelLabels
    model_id: str

    @property
    def modle_id(self) -> str:
        return REMOTES[self.model_label]

    @property
    def model_dir_name(self) -> str:
        return self.model_label

    @property
    def is_a_streaming_model(self) -> bool:
        return self.model_label in STREAMING_MODELS


class KokoroRepo(RepoSpec):

    model_label: ModelLabels = ModelLabels.KOKORO
    model_id: str = REMOTES[model_label]
    source_params_filename: str = "config.json"
    params_filename: str = "params.json"

    WEIGHTS_FILES: dict = {
            ModelLabels.KOKORO:
            'kokoro-v1_0.pth',

            ModelLabels.KOKORO_V1:
            'kokoro-v1_1-zh.pth',
            }

    MANIFEST: list[str] = [
            WEIGHTS_FILES[model_label],
            "config.json"
            ]

    @property
    def weights_filename(self):
        return self.WEIGHTS_FILES[self.model_label]


class KrokoRepo(RepoSpec):

    MANIFEST: list[str] = []
    model_label: ModelLabels =  ModelLabels.ENGLISH_RECOGNIZER
    model_id: str = REMOTES[model_label]
    model_type: str = RecognizerType.ZIPFORMER
    onnx: bool = True


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

