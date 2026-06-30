import os
import json
from pathlib import Path
from typing import Any, ClassVar
from abc import ABC, abstractmethod
from pfspeak.core.param import SpeechParams
from pfspeak.common.just_checking import TypeTensor
from pfspeak.common.defaults import AppSpec, RepoSpec
from pfspeak.core.repo import RecognizerRepo, SpeechRepo
from huggingface_hub import hf_hub_download, snapshot_download


class Asset(ABC):
    registry: ClassVar[list[type["Asset"]]] = []

    subsystem: ClassVar[str]

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        Asset.registry.append(cls)

    @staticmethod
    def root(app: AppSpec, repo: RepoSpec):
        return app.models_dir / repo.model_dir_name

    @staticmethod
    def installer(app_spec: AppSpec, runtime_spec, filename: str | None = None):

        def resolve_hf_token() -> str | bool:
            if token := os.getenv("HF_TOKEN"):
                return token
            else:
                return False

        kwargs = {
                'cache_dir': app_spec.cache_dir,
                'local_dir': app_spec.models_dir / runtime_spec.model_dir_name,
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

    @classmethod
    @abstractmethod
    def verify(cls, app, repo) -> bool: ...

    @classmethod
    @abstractmethod
    def load(cls, app, repo, *args) -> Any: ...

    @classmethod
    @abstractmethod
    def download(cls, app, repo, *args) -> Any: ...

    @classmethod
    def fail_on_missing(cls, app: AppSpec, repo: SpeechRepo):
        if not cls.verify(app, repo):
            raise FileNotFoundError("Speech model weight file not found")


class SpeechWeights(Asset):
    subsystem = "tts"

    @classmethod
    def verify(cls, app: AppSpec, repo: SpeechRepo):
        file = cls.root(app, repo) / repo.weights_filename
        return file.exists()

    @classmethod
    def load(cls, app: AppSpec, repo: SpeechRepo, *_) -> TypeTensor:
        import torch
        return torch.load(cls.root(app, repo) / repo.weights_filename)

    @classmethod
    def download(cls, app: AppSpec, repo: SpeechRepo, *_):
        file = cls.root(app, repo) / repo.weights_filename
        if not cls.verify(app, repo):
            _ = cls.installer(app, repo, repo.weights_filename)
            if not cls.verify(app, repo):
                raise RuntimeError("Failed to download speech model weights")
        return file


class SpeechParamsAsset(Asset):
    subsystem = "tts"

    @classmethod
    def verify(cls, app: AppSpec, repo: SpeechRepo):
        return (cls.root(app, repo) / repo.params_filename).exists()

    @classmethod
    def load(cls, app: AppSpec, repo: SpeechRepo, *_):
        params_file = cls.root(app, repo) / repo.params_filename
        return SpeechParams(**json.loads(params_file.read_text()))

    @classmethod
    def fail_on_missing(cls, app: AppSpec, repo: SpeechRepo):
        if not cls.verify(app, repo):
            raise FileNotFoundError("Speech model weight file not found")

    @classmethod
    def download(cls, app: AppSpec, repo: SpeechRepo, *_):
        file = cls.root(app, repo) / repo.params_filename
        if not cls.verify(app, repo):
            _ = cls.installer(app, repo, repo.params_filename)
            if not cls.verify(app, repo):
                raise RuntimeError("Failed to download speech model weights")
        return file



class SpeechVoiceAsset(Asset):
    subsystem = "tts"

    @classmethod
    def verify(cls, app: AppSpec, repo: SpeechRepo, *args):
        voice_label = args[0]
        local_dir = app.models_dir / repo.model_dir_name 
        return (local_dir / repo.voice_filename(voice_label)).exists()

    @classmethod
    def load(cls, app: AppSpec, repo: SpeechRepo, *args):
        import torch
        voice_label = args[0]
        local_dir = app.models_dir / repo.model_dir_name 
        weights_file = local_dir / repo.voice_filename(voice_label)
        return torch.load(weights_file, map_location="cpu", weights_only=True)

    @classmethod
    def download(cls, app: AppSpec, repo: SpeechRepo, *args):
        voice_label = args[0]
        if not cls.verify(app, repo):
            _ = cls.installer(app, repo, voice_label)
            if not cls.verify(app, repo):
                raise RuntimeError("Failed to download speech model weights")
        return True


class RecognizerAsset(Asset):
    subsystem = "stt"

    @classmethod
    def verify(cls, app: AppSpec, repo: RecognizerRepo):
        model_dir = cls.root(app, repo) / repo.model_dir_name
        for filename in repo.MANIFEST:
            if not (model_dir / filename).exists():
                return False
        return True

    @classmethod
    def load(cls, app: AppSpec, repo: RecognizerRepo, *args):
        params = args[0]
        def abs_path(value: str):
            return str(model_dir / value)

        model_dir = app.models_dir / repo.model_dir_name

        if not model_dir.exists():
            print(model_dir)
            raise RuntimeError("Could not find model in data root directory")

        if not repo.is_a_streaming_model:
            raise RuntimeError("Don't forget to get the streaming model.")

        kwargs = dict()
        if params.hot_words:
            kwargs["decoding_method"] = "modified_beam_search"
            kwargs["hotwords_score"] = float(params.hot_words_bias)
            kwargs["hot_words"] = " ".join(params.hot_words)

        from sherpa_onnx import OnlineRecognizer
        return OnlineRecognizer.from_transducer(
            tokens=abs_path(repo.tokens),
            encoder=abs_path(repo.encoder),
            decoder=abs_path(repo.decoder),
            joiner=abs_path(repo.joiner),
            num_threads=params.treads,
            sample_rate=params.samplerate,
            feature_dim=params.feature_dim,
            **kwargs,
            )

    @classmethod
    def download(cls, app: AppSpec, repo: RecognizerRepo, *_):
        file = cls.root(app, repo) / repo.model_dir_name
        if not cls.verify(app, repo):
            _ = cls.installer(app, repo)
            if not cls.verify(app, repo):
                raise RuntimeError("Failed to download speech model weights")
        return file


def follow_policy(app: AppSpec, repo: RepoSpec, subsystem: str):
    for asset in Asset.registry:
        if asset.subsystem != subsystem:
            continue

        if not asset.verify(app, repo):
            asset.download(app, repo)
