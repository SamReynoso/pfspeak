import sys
import tomllib
from pathlib import Path

from pfspeak.common.defaults import DEFAULT_APP_SPEC as default

from pydantic import BaseModel


class PfSpeakConfig(BaseModel):

    version: str = default.version
    org_name: str = default.org_name
    app_name: str = default.app_name
    pipe_path: Path = default.cache_dir / "daemon.pipe"
    ready_file: Path = default.cache_dir / "daemon.status"
    messages_dir: Path = default.data_dir / "messages"
    play_system_messages: bool = True

    lang: str
    voice: str
    speech_speed: float
    log_level: str

    latency: float = 0.2
    samplerate: int = 24_000
    queue_size: int = 510


class CommandlineArgs:
    regenerate: bool = '--regenerate' in sys.argv
    silent: bool = '--silent' in sys.argv
    verbose: bool = '--verbose' in sys.argv
    import_check: bool = '--import-check' in sys.argv
    config: bool = '--config' in sys.argv
    verify: bool = '--verify' in sys.argv

    help: bool = 'help' in sys.argv or "--help" in sys.argv
    install: bool = 'install' in sys.argv or "--install" in sys.argv
    test: bool = 'test' in sys.argv or "--test" in sys.argv

    speak: bool = 'speak' in sys.argv
    listen: bool = 'listen' in sys.argv


commandline_args = CommandlineArgs()


_toml_template = f"""# {default.config_file}

lang = "a"
voice = "bf_lily"
speech_speed = 1.0
log_level = "DEBUG"
"""


pfconfig = PfSpeakConfig(**tomllib.loads(_toml_template))

print(pfconfig.voice)

