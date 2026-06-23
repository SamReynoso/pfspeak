from pathlib import Path

from pydantic import BaseModel


class AppSpec(BaseModel):
    version: str
    org_name: str
    app_name: str

    data_dir: Path
    cache_dir: Path
    config_dir: Path

    config_file: Path


