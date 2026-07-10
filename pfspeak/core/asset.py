import os
import json
from abc import ABC
from pathlib import Path
from typing import ClassVar

from pfspeak.common.types import VoiceLable
from pfspeak.common.just_checking import TypeTensor
from pfspeak.common.defaults import AppSpec, RepoSpec
from pfspeak.core.types import ServiceTypes,LoadPolicy
from pfspeak.core.repo import RecognizerRepo, SpeechRepo
from pfspeak.core.param import ListenParams, SpeechParams


class Asset(ABC):
    registry: ClassVar[list[type["Asset"]]] = []

    subsystem: ServiceTypes

    policy: LoadPolicy

    def __init__(self, app: AppSpec, repo: RepoSpec) -> None:
        super().__init__()
        self.app = app
        self.repo = repo
        self.filename: str | None = None

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        Asset.registry.append(cls)

    @property
    def root(self):
        return self.app.models_dir / self.repo.model_dir_name

    def verify(self):
        root = self.app.models_dir / self.repo.model_dir_name
        if not self.filename:
            return root.exists()
        file = root / self.filename
        return file.exists()

    def fail_on_missing(self) -> None:
        if not self.verify():
            raise FileNotFoundError("Speech model weight file not found")


    def install(self):
        from huggingface_hub import hf_hub_download, snapshot_download

        def resolve_hf_token() -> str | bool:
            if token := os.getenv("HF_TOKEN"):
                return token
            else:
                return False

        kwargs = {
                'cache_dir': self.app.cache_dir,
                'local_dir': self.app.models_dir / self.repo.model_dir_name,
                'token': resolve_hf_token(),
                }

        if self.filename:
            return Path(
                    hf_hub_download(
                        self.repo.model_id,
                        self.filename,
                        **kwargs)
                    )
        else:
            return Path(
                    snapshot_download(
                        self.repo.model_id,
                        **kwargs)
                    )

    def ensure(self):
        if not self.verify():
            self.install()


class SpeechWeights(Asset):

    subsystem = ServiceTypes.TTS

    policy = LoadPolicy.EAGER

    def __init__(self, app: AppSpec, repo: SpeechRepo) -> None:
        super().__init__(app, repo)
        self.filename = repo.weights_filename

    def load(self) -> TypeTensor:
        import torch
        assert self.filename
        return torch.load(self.root / self.filename, map_location="cpu")


class SpeechParamsAsset(Asset):

    subsystem = ServiceTypes.TTS

    policy = LoadPolicy.EAGER

    def __init__(self, app: AppSpec, repo: SpeechRepo) -> None:
        super().__init__(app, repo)
        self.filename = repo.params_filename

    def load(self):
        assert self.filename
        params_file = self.root / self.filename
        return SpeechParams(**json.loads(params_file.read_text()))


class SpeechVoiceAsset(Asset):
    subsystem = ServiceTypes.TTS

    policy = LoadPolicy.LAZY

    def load(self, voice_label: VoiceLable):
        self.filename = f"voices/{voice_label}.pt"
        self.ensure()
        import torch
        weights_file = self.root / self.filename
        return torch.load(weights_file, map_location="cpu", weights_only=True)


class RecognizerAsset(Asset):

    subsystem = ServiceTypes.STT

    policy = LoadPolicy.EAGER

    def __init__(self,
                 app: AppSpec,
                 repo: RecognizerRepo,
                 ) -> None:
        super().__init__(app, repo)
        self.repo = repo

    def load(self, params: ListenParams):

        def abs_path(value: str):
            return str(self.root / value)

        if not self.root.exists():
            raise RuntimeError("Could not find model in data root directory")

        if not self.repo.is_a_streaming_model:
            raise RuntimeError("Don't forget to get the streaming model.")

        kwargs = dict()
        if params.hot_words:
            kwargs["decoding_method"] = "modified_beam_search"
            kwargs["hotwords_score"] = float(params.hot_words_bias)
            kwargs["hot_words"] = " ".join(params.hot_words)

        from sherpa_onnx import OnlineRecognizer
        return OnlineRecognizer.from_transducer(
            tokens=abs_path(self.repo.tokens),
            encoder=abs_path(self.repo.encoder),
            decoder=abs_path(self.repo.decoder),
            joiner=abs_path(self.repo.joiner),
            num_threads=params.treads,
            sample_rate=params.samplerate,
            feature_dim=params.feature_dim,
            **kwargs,
            )


def follow_policy(app: AppSpec, repo: RepoSpec, subsystem: ServiceTypes):
    for asset_class in Asset.registry:
        if asset_class.subsystem != subsystem:
            continue

        if asset_class.policy != LoadPolicy.EAGER:
            continue

        asset = asset_class(app, repo)

        if not asset.verify():
            asset.install()
