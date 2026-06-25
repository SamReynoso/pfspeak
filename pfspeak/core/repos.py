import json
from pathlib import Path
from .params import ListenParams, SpeechParams
from pfspeak.core.tts.inference import SpeechModel
from pfspeak.common.defaults import AppSpec, KokoroRepo, KrokoRepo
from pfspeak.common.just_checking import TypeRecognizer


class SpeechRepo(KokoroRepo):

    @staticmethod
    def voice_weights_filename(voice_label: str) -> str:
        return f"voices/{voice_label}.pt"

    @staticmethod
    def to_params(params_file: Path) -> SpeechParams:
        return SpeechParams(**json.loads(params_file.read_text()))

    def to_inference_model(self, app: AppSpec) -> SpeechModel:
        params_file =  self.local_dir(app) / self.params_filename
        return SpeechModel(self.to_params(params_file))

class RecognizerRepo(KrokoRepo):

    tokens: str= "tokens.txt"

    @property
    def postfix(self) -> str:
        if self.onnx:
            return ".onnx"
        return ""

    def with_postfix(self, filename: str) -> str:
        return filename + self.postfix

    @property
    def encoder(self) -> str:
        return  self.with_postfix("encoder")

    @property
    def decoder(self) -> str:
        return self.with_postfix("decoder")

    @property
    def joiner(self) -> str:
        return self.with_postfix("joiner")

    def to_recognizer(self,
                      app: AppSpec,
                      params: ListenParams
                      ) -> TypeRecognizer:
        def abs_path(value: str):
            return str(model_dir / value)

        model_dir = app.models_dir / self.model_dir_name

        if not model_dir.exists():
            raise RuntimeError("Could not find model in data root directory")

        if not self.is_a_streaming_model:
            raise RuntimeError("Don't forget to get the streaming model.")

        kwargs = dict()
        if params.hot_words:
            kwargs["decoding_method"] = "modified_beam_search"
            kwargs["hotwords_score"] = float(params.hot_words_bias)
            kwargs["hot_words"] = " ".join(params.hot_words)

        from sherpa_onnx import OnlineRecognizer
        return OnlineRecognizer.from_transducer(
            tokens=abs_path(self.tokens),
            encoder=abs_path(self.encoder),
            decoder=abs_path(self.decoder),
            joiner=abs_path(self.joiner),
            num_threads=params.treads,
            sample_rate=params.samplerate,
            feature_dim=params.feature_dim,
            **kwargs,
        )
