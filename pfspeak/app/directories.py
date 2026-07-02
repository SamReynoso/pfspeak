try:
    import tomllib
except ImportError:
    import tomli as tomllib

import sys
from pfspeak.app import pfconfig
from pfspeak.app import PfSpeakConfig
from pfspeak.common.defaults import AppSpec


def build(app: AppSpec):

    for app_dir in (app.cache_dir, app.data_dir, app.config_dir):
        try:
            if not app_dir.exists():
                app_dir.mkdir(parents=True, exist_ok=True)
                print("Created:", app_dir)
        except Exception:
            sys.stderr.write("Could not create application directory\n" 
                             f"Path: '{app_dir}'\n")
            sys.exit(1)

    try:
        if not app.config_file.exists():
            print("Creating defualt configuration file")
            app.config_file.write_text(PfSpeakConfig.toml_template)
            print("Created:", app.config_file)
    except Exception:
        sys.stderr.write("Failed to create configuration file\n"
                         f"Path: '{app.config_file}'")
        sys.exit(1)

    try:
        if app.config_file.exists():
            with app.config_file.open("rb") as f:
                _config_toml_data = tomllib.load(f)
            for k, v in _config_toml_data.items():
                setattr(pfconfig, k, v)
            print("App: configuration loaded")
        else:
            sys.stderr.write("Failed to load pfspeak.toml\n"
                             f"Path: {app.config_file}")
            sys.exit(1)
    except Exception:
        sys.stderr.write("Failed to parse configuration file\n"
                         f"Path: {app.config_file}\n")
        sys.exit(1)

    return pfconfig
