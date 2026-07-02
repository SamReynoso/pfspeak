from pfspeak.common import defaults 
from pfspeak.common.types import VoiceLable
from pfspeak.common.defaults import RepoSpec 
from pfspeak.core.param import RecognizerType


class SpeechRepo(RepoSpec):
    model_label: defaults.ModelLabels = defaults.ModelLabels.KOKORO
    model_id: str = defaults.REMOTES[model_label]
    params_filename: str = "config.json"

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
    def voice_filename(voice_label: VoiceLable) -> str:
        return f"voices/{voice_label}.pt"


class RecognizerRepo(RepoSpec):

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
    def tokens(self) -> str:
        return  "tokens.txt"

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
