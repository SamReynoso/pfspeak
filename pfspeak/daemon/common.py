from pathlib import Path
from pydantic import BaseModel

from pfspeak.common.defaults import DEFAULT_APP_SPEC as default


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

