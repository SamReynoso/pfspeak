from pathlib import Path
import sys
import time

from pfspeak.common.defaults import DEFAULT_APP_SPEC as default
from pfspeak.stt.runtime import KrokoRecognizerSpec, SpeechToText
from pfspeak.common.defaults import AppSpec
from queue import Queue
from threading import Thread

commands = Queue()

class PfListenConfig(AppSpec):
    version: str = default.version
    org_name: str = default.org_name
    app_name: str = "pflisten"

    data_dir: Path = default.data_dir
    cache_dir: Path = default.cache_dir
    config_dir: Path = default.config_dir

    config_file: Path = default.config_dir / "pflisten.toml"
    latency: float = 0.2


def fw(text: str):
    los = 0
    for word in text.split():
        if los >= 60:
            los = 0
        if los == 0:
            sys.stdout.write("\n\t")
        sys.stdout.write(f"{word} ")
        los += len(word) + 1
    sys.stdout.flush()

def keyboard():
    while True:
        cmd = input()
        if not cmd != []:
            cmd = "foobar"
        commands.put(cmd)


def listen(**_):


    app_spec = PfListenConfig()
    recognizer_spec = KrokoRecognizerSpec()
    runtime = SpeechToText(app_spec, recognizer_spec)

    buffer = []

    Thread(target=keyboard, daemon=True).start()

    temp = None
    val = ""
    with runtime:
        while val.upper() != "EXIT":
            print(f"""\x1b[2J\x1b[H
    Commands:
    (any key + ENTER) commit partioals to the final area
    (exit + ENTER) to exit.

    Bonus:
    (speak)

{"-" * 40}
    FINAL
""", end="")

            for ret in buffer:
                fw(ret.text)
                print()

            print(f"""
{"-" * 40}
    PARTIAL""")
            if temp:
                fw(temp.text)
                print(temp.tokens.count, len(temp.tokens), len(temp.waveform))

            if not commands.empty():
                val = commands.get().upper()

                match val:
                    case "EXIT":
                        return
                    case "REPEAT":
                        import sounddevice as sd
                        if temp:
                            print("playing")
                            sd.play(temp.waveform, samplerate=16_000)
                            print(temp.text)
                            sd.wait()

                    case _:
                        temp = None
                        ret = runtime.next()
                        if ret:
                            buffer.append(ret)

            if ret := runtime.read():
                temp = ret

            time.sleep(4)

