import os
import sys
import time
import tomllib
from importlib.util import find_spec
from multiprocessing import Process
from pfspeak.common.defaults import DEFAULT_APP_SPEC as default
from pfspeak.services import pfconfig, commandline_args, _toml_template


from pfspeak.services.listen import listen



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
        sys.exit(1)

try:
    if not pfconfig.pipe_path.exists():
        os.mkfifo(pfconfig.pipe_path)
except Exception:
    sys.stderr.write("Could not create daemon pipe\n")
    sys.exit(1)

try:
    if not default.config_file.exists() or commandline_args.regenerate:
        default.config_file.write_text(_toml_template)
except Exception:
    sys.stderr.write("Failed to create configuration file\n")
    sys.exit(1)


try:
    if default.config_file.exists():
        with default.config_file.open("rb") as f:
            _config_toml_data = tomllib.load(f)
    elif commandline_args.test:
        _config_toml_data = tomllib.loads(_toml_template)
    else:
        raise RuntimeError
except Exception:
    sys.stderr.write("Failed to load pfspeak.toml\n")
    sys.exit(1)


try:
    for k, v in _config_toml_data.items():
        setattr(pfconfig, k, v)
except Exception:
    sys.stderr.write("Failed to parse configuration file\n")
    sys.stderr.write(f"Path: {default.config_file}\n")
    print(_config_toml_data)
    sys.exit(26)


if __name__ == "__main__":

    if commandline_args.verify:
        from pfspeak.cli.verify import verify_all
        exit(verify_all(commandline_args))

    if commandline_args.config:
        from pfspeak.cli.messages import config_output
        print(config_output)
        sys.exit(0)

    elif commandline_args.help:
        from pfspeak.cli.messages import help_output
        print(help_output)
        sys.exit(0)

    elif commandline_args.install:
        from pfspeak.services.install import install
        install(pfconfig)

    elif commandline_args.test:
        print("Testing pfspeak daemon:")
        from pfspeak.services.speak import serve
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

            print("Writing test message")
            with open(pfconfig.pipe_path, "w") as f:
                f.write("PfSpeak integration test.\n$SHUTDOWN\n")
            p.join()
            sys.exit(p.exitcode)
        except KeyboardInterrupt:
            sys.exit(1)
        finally:
            p.kill()
            pfconfig.pipe_path.unlink(missing_ok=True)

    elif commandline_args.listen:
        print("Starting...")
        listen(time_to_live=120)
        print("goodbye.")


    elif commandline_args.speak:
        print("Starting pfspeak speak:")
        from pfspeak.services.speak import serve
        ret = serve()
        sys.exit(ret)

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
    else:
        sys.stderr.write("Error: no commands provided. Use pfspeak help for more\n")
        exit(1)
sys.exit(0)
