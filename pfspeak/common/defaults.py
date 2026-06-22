from enum import StrEnum
from pathlib import Path

from platformdirs import PlatformDirs

from pfspeak.tts.specs import AppSpec


MODEL_NAMES = {
        'hexgrad/Kokoro-82M': 'kokoro-v1_0.pth',
        'hexgrad/Kokoro-82M-v1.1-zh': 'kokoro-v1_1-zh.pth',
        "sherpa-zipformer": "sherpa-onnx-streaming-zipformer-en-kroko-2025-08-06",
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

        config_file=Path(_platform_dirs.user_config_dir) / "_app_name.toml",
        )

