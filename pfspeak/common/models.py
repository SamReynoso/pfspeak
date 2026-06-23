import os

from pathlib import Path
from typing import Optional

from huggingface_hub import hf_hub_download, snapshot_download

from pfspeak.common.defaults import AppSpec, RuntimeSpec


def install_model(app_spec: AppSpec, runtime_spec: RuntimeSpec):

    def resolve_hf_token() -> str | bool:
        if token := os.getenv("HF_TOKEN"):
            return token
        else:
            return False

    def download(filename: Optional[str] = None) -> Path:

        kwargs = {
                'cache_dir': app_spec.cache_dir,
                'local_dir': runtime_spec.resolv_local_dir(app_spec),
                'token': resolve_hf_token(),
                }

        if filename:
            return Path(
                    hf_hub_download(
                        runtime_spec.model_id,
                        filename,
                        **kwargs)
                    )
        else:
            return Path(
                    snapshot_download(
                        runtime_spec.model_id,
                        **kwargs)
                    )

    return download
