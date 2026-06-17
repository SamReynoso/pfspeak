# PfSpeak runtime

from importlib.util import find_spec
import os
import sys
import time
import tomllib
import subprocess
from multiprocessing import Process
from pathlib import Path

from pfspeak.core.defaults import DEFAULT_APP_SPEC as default


from pydantic import BaseModel



class CommandlineArgs:
    regenerate: bool = '--regenerate' in sys.argv
    silent: bool = '--silent' in sys.argv
    bootstrap: bool = '--bootstrap' in sys.argv
    verbose: bool = '--verbose' in sys.argv
    messages: bool = '--messages' in sys.argv
    import_check: bool = '--import-check' in sys.argv
    help: bool = '--help' in sys.argv
    config: bool = '--config' in sys.argv

    install: bool = 'install' in sys.argv
    serve: bool = 'serve' in sys.argv
    test: bool = 'test' in sys.argv


commandline_args = CommandlineArgs()


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


_toml_template = f"""# {default.config_file}

lang = "a"
voice = "bf_lily"
speech_speed = 1.0
log_level = "DEBUG"
"""


pfconfig = PfSpeakConfig(**tomllib.loads(_toml_template))


if commandline_args.install or commandline_args.regenerate:
    for app_dir in (default.cache_dir,
                    default.data_dir,
                    default.config_dir,
                    pfconfig.messages_dir,):
        try:
            app_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            sys.stderr.write("Could not create application directory " 
                             f"'{app_dir}'\n"
                             )
            sys.exit(22)

    try:
        if not pfconfig.pipe_path.exists():
            os.mkfifo(pfconfig.pipe_path)
    except Exception:
        sys.stderr.write("Could not create daemon pipe\n")
        sys.exit(23)

    try:
        if not default.config_file.exists() or commandline_args.regenerate:
            default.config_file.write_text(_toml_template)
    except Exception:
        sys.stderr.write("Failed to create configuration file\n")
        sys.exit(24)


try:
    if default.config_file.exists():
        with default.config_file.open("rb") as f:
            _config_toml_data = tomllib.load(f)
    elif commandline_args.test:
        _config_toml_data = tomllib.loads(_toml_template)
    else:
        raise RuntimeError
except Exception:
    sys.stderr.write(
            "Failed to load pfspeak.toml\n"
            "Run with pfspeak install first\n"
            )
    sys.exit(25)


try:
    for k, v in _config_toml_data.items():
        setattr(pfconfig, k, v)
except Exception as e:
    sys.stderr.write("Failed to parse configuration file\n")
    sys.stderr.write(f"Path: {default.config_file}\n")
    print(_config_toml_data)
    raise e


if __name__ == "__main__":

    if commandline_args.config:
        from messages import config_output
        print(config_output)
        sys.exit(0)

    elif commandline_args.help:
        from messages import help_output
        print(help_output)
        sys.exit(0)

    elif commandline_args.install:
        env = os.environ.copy()
        env["PFREADY"] = str(pfconfig.ready_file)
        env["PFSPEAK"] = str(pfconfig.pipe_path)
        env["PFLOG_LEVEL"] = "INFO"
        sys.exit(
                subprocess.run(
                    ["sh", "./daemon/install.sh"],
                    env=env
                    ).returncode
                )

    elif commandline_args.test:
        from service import serve
        p = Process(target=serve)
        p.start()
        i = 0
        try:
            while not pfconfig.ready_file.exists():
                i += 1
                time.sleep(pfconfig.latency)
                if i >= 20 / pfconfig.latency:
                    p.kill()
                    sys.exit(1)
            with open(pfconfig.pipe_path, "w") as f:
                f.write("PfSpeak integration test.\n$SHUTDOWN\n")
            p.join()
            sys.exit(p.exitcode)
        except KeyboardInterrupt:
            p.kill()
            sys.exit(1)

    elif commandline_args.serve:
        print("Starting pfspeak service")
        from daemon.service import serve
        ret = serve()
        sys.exit(ret)

    elif commandline_args.messages:
        from messages import Q
        for k, _ in Q:
            print(k)

    elif commandline_args.import_check:
        requierd = (
                "sounddevice",
                "torch",
                "huggingface_hub",
                "spacy",
                "misaki"
                )
        for mod in requierd:
            if find_spec(mod) is None:
                sys.stderr.write(f"Missing dependency: {mod}\n")
                sys.exit(50)
    sys.exit(0)
