from enum import StrEnum
from pathlib import Path

from platformdirs import PlatformDirs
from pydantic import BaseModel


MODEL_NAMES = {
        'hexgrad/Kokoro-82M':
        'kokoro-v1_0.pth'
        ,
        'hexgrad/Kokoro-82M-v1.1-zh':
        'kokoro-v1_1-zh.pth'
        ,
        "sherpa-zipformer":
        "csukuangfj/sherpa-onnx-streaming-zipformer-en-kroko-2025-08-06"
        ,
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
    AF_BELLA = "af_bella"

class AppSpec(BaseModel):
    version: str
    org_name: str
    app_name: str

    data_dir: Path
    cache_dir: Path
    config_dir: Path

    config_file: Path


class RuntimeSpec(BaseModel):
    model_id: str
    model_label: str | None = None
    weights_file: Path | None = None
    use_model_dir: bool = True

    def resolv_local_dir(self, app_spec: AppSpec):
        if self.use_model_dir:
            root = app_spec.data_dir / "models"
        else:
            root = app_spec.data_dir

        if self.model_label:
            return root / self.model_label
        else:
            return root / self.model_id

    # model_source: Literal[
    #         "local",
    #         "huggingface",
    #         ] = "huggingface"
    # voice_source: Literal[
    #         "local",
    #         "huggingface",
    #         ] = "huggingface"
    # token: str | None = None
    # env_token_name: str | None = None
    # discover_token: bool = True

    # use_provider_config: bool = True
    # raise_for_errors: bool = True
    # auto_download: bool = True
    # preload: bool = True
    # verify: bool = True
    # local_only: bool = False
    # lazy_load: bool = False
    # offline: bool = False


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

