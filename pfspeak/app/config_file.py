import os
import sys
import tomllib
from pfspeak.common.defaults import DEFAULT_APP_SPEC as default
from pfspeak.app import pfconfig, commandline_args, _toml_template


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
