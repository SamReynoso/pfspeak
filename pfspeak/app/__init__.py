try:
    import tomllib
except ImportError:
    import tomli as tomllib

import os
from dataclasses import dataclass
from pathlib import Path
from pfspeak.common.defaults import DEFAULT_APP_SPEC as default


os.environ["HF_HOME"] = str(default.models_dir)


@dataclass(slots=True)
class PfSpeakConfig:

    lang: str
    voice: str
    speech_speed: float
    log_level: str

    pipe_path: Path = default.cache_dir / "daemon.pipe"
    ready_file: Path = default.cache_dir / "daemon.status"

    toml_template = f"""# {default.config_file}

    lang = "a"
    voice = "bf_lily"
    speech_speed = 1.0
    log_level = "DEBUG"
    """

    @classmethod
    def defualt(cls):
        return cls(**tomllib.loads(cls.toml_template))


pfconfig = PfSpeakConfig.defualt()
