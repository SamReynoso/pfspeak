import os
import json

from pathlib import Path

from huggingface_hub import hf_hub_download, snapshot_download

from pfspeak.common.defaults import AppSpec
from pfspeak.core.params import ListenParams, SpeechParams
from pfspeak.core.repos import RecognizerRepo, SpeechRepo
from pfspeak.core.tts.inference import SpeechModel
from pfspeak.common.just_checking import TypeRecognizer


def inference_model_params(app: AppSpec, repo: SpeechRepo):
    params_file = app.models_dir / repo.params_filename
    return SpeechParams(**json.loads(params_file.read_text()))


def inference_model(app: AppSpec, repo: SpeechRepo):
    return SpeechModel(inference_model_params(app, repo))


def recognizer(app: AppSpec,
               repo: RecognizerRepo,
               params: ListenParams
               ) -> TypeRecognizer:
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



def install_model(app_spec: AppSpec, runtime_spec):

    def resolve_hf_token() -> str | bool:
        if token := os.getenv("HF_TOKEN"):
            return token
        else:
            return False

    def download(filename: str | None = None) -> Path:

        kwargs = {
                'cache_dir': app_spec.cache_dir,
                'local_dir': app_spec.local_dir / runtime_spec.model_dir_name,
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
