import os
import sys
import tomllib
from pfspeak.app import pfconfig, _toml_template
from pfspeak.common.defaults import AppSpec


def build(app: AppSpec):
    for app_dir in (app.cache_dir, app.data_dir, app.config_dir):
        try:
            app_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            sys.stderr.write("Could not create application directory " 
                             f"'{app_dir}'\n"
                             )
            sys.exit(1)

    try:
        if not app.config_file.exists():
            app.config_file.write_text(_toml_template)
    except Exception:
        sys.stderr.write("Failed to create configuration file\n")
        sys.exit(1)

    try:
        if app.config_file.exists():
            with app.config_file.open("rb") as f:
                _config_toml_data = tomllib.load(f)
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
        sys.stderr.write(f"Path: {app.config_file}\n")
        sys.exit(1)

    return pfconfig
