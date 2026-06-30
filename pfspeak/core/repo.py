import json
from pathlib import Path
from .param import SpeechParams
from dataclasses import dataclass
from pfspeak.common import defaults 
from pfspeak.core.param import RecognizerType
from pfspeak.common.defaults import RepoSpec 


class SpeechRepo(RepoSpec):
    model_label: defaults.ModelLabels = defaults.ModelLabels.KOKORO
    model_id: str = defaults.REMOTES[model_label]
    source_params_filename: str = "config.json"
    params_filename: str = "params.json"

    WEIGHTS_FILES: dict = {
            defaults.ModelLabels.KOKORO:
            'kokoro-v1_0.pth',

            defaults.ModelLabels.KOKORO_V1:
            'kokoro-v1_1-zh.pth',
            }

    MANIFEST: list[str] = [
            WEIGHTS_FILES[model_label],
            "config.json"
            ]

    @property
    def weights_filename(self):
        return self.WEIGHTS_FILES[self.model_label]

    @staticmethod
    def voice_filename(voice_label: str) -> str:
        return f"voices/{voice_label}.pt"


    @staticmethod
    def to_params(params_file: Path) -> SpeechParams:
        return SpeechParams(**json.loads(params_file.read_text()))


class RecognizerRepo(RepoSpec):

    tokens: str= "tokens.txt"

    model_label: defaults.ModelLabels =  defaults.ModelLabels.ENGLISH_RECOGNIZER
    model_id: str = defaults.REMOTES[model_label]
    model_type: str = RecognizerType.ZIPFORMER
    onnx: bool = True


    MANIFEST: list[str] = [
            "tokens.txt",
            "encoder.onnx",
            "decoder.onnx",
            "joiner.onnx",
            ]

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
