from pathlib import Path
import time

from pfspeak.common.defaults import DEFAULT_APP_SPEC as default
from pfspeak.stt.runtime import KrokoRecognizerSpec, SpeechToText
from pfspeak.common.defaults import AppSpec


class PfListenConfig(AppSpec):
    version: str = default.version
    org_name: str = default.org_name
    app_name: str = "pflisten"

    data_dir: Path = default.data_dir
    cache_dir: Path = default.cache_dir
    config_dir: Path = default.config_dir

    config_file: Path = default.config_dir / "pflisten.toml"
    latency: float = 0.2


def listen(time_to_live: int = 12):

    TIME_TO_LIVE = time_to_live

    app_spec = PfListenConfig()
    recognizer_spec = KrokoRecognizerSpec()
    runtime = SpeechToText(app_spec, recognizer_spec)
    START_TIME = time.time()
    print("Ready...")

    @runtime.on_final
    def on_final(final):
        print(final.text)

    @runtime.kill_on 
    def kill_on():
        return time.time() - START_TIME > TIME_TO_LIVE

    with runtime:
        runtime.runforever()
