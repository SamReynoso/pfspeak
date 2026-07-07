import sys
import os
import subprocess
from importlib.resources import files, as_file

from pfspeak.app import PfSpeakConfig

def install(pfconfig: PfSpeakConfig):
    env = os.environ.copy()
    env["PFREADY"] = str(pfconfig.ready_file)
    env["PFSPEAK"] = str(pfconfig.pipe_path)
    env["PFLOG_LEVEL"] = "INFO"

    with as_file(files("pfspeak").joinpath("resources/install.sh")) as script:
        env["PFROOT"] =  str(script.parent)
        sys.exit(
                subprocess.run(
                    ["sh", str(script)],
                    env=env
                    ).returncode
                )
