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
    log_level: str
    speech_speed: float

    latency: float = 0.2
    samplerate: int = 24_000
    queue_size: int = 510

    version: str = default.version
    org_name: str = default.org_name
    app_name: str = default.app_name
    pipe_path: Path = default.cache_dir / "daemon.pipe"
    ready_file: Path = default.cache_dir / "daemon.status"
    messages_dir: Path = default.data_dir / "messages"


_toml_template = f"""# {default.config_file}

lang = "a"
voice = "bf_lily"
speech_speed = 1.0
log_level = "DEBUG"
"""

pfconfig = PfSpeakConfig(**tomllib.loads(_toml_template))
