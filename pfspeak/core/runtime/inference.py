import sys
from types import ModuleType
from typing import Dict, Literal
from pfspeak.core.asset import (
        SpeechWeights,
        SpeechVoiceAsset,
        SpeechParamsAsset
        )
from pfspeak.core.repo import SpeechRepo
from pfspeak.common.defaults import AppSpec
from pfspeak.common.dataclasses import CudaSupport
from pfspeak.common.exceptions import ArchitectureNotInitializeError
from pfspeak.common.just_checking import TypeArchitecture, TypeTensor
from pfspeak.extra.decorators import architecture_initialized, torch_imported


class SpeechModel:
    def __init__(self,
                 app: AppSpec,
                 repo: SpeechRepo,
                 ) -> None:
        self.app = app
        self.repo = repo
        self.loaded: bool = False
        self.torch: ModuleType | None = None
        self.voices: Dict[str, TypeTensor] = {}
        self.arch: TypeArchitecture | None = None
        self.params = SpeechParamsAsset(app, repo).load()


    @property
    def max_phonemes(self):
        if not self.arch:
            # NOTE: Maybe expose this through self.params
            raise ArchitectureNotInitializeError(
            "Maximum phoneme length is unavailable until the model "
            "architecture has been initialized.")
        return self.arch.bert.config.max_position_embeddings

    def load_model(self) -> None:
        self.load_weights()
        self.to_device()
        self.to_inference_mode()

    def to_device(self, device: str | None = None):
        self.raise_for_missing_weights()
        assert self.arch and self.params
        self.device = self.resolve_device_label(device or self.params.device)
        self.arch.to(self.device)
        return self

    def to_inference_mode(self):
        self.raise_for_missing_weights()
        assert self.arch
        return self.arch.eval()

    @architecture_initialized
    def load_weights(self) -> None:
        assert self.params and self.torch
        loaded =  SpeechWeights(self.app, self.repo).load()
        for key, state_dict in loaded.items():
            try:
                getattr(self.arch, key).load_state_dict(state_dict)
            except Exception:
                state_dict = {k[7:]: v for k, v in state_dict.items()}
                getattr(self.arch, key).load_state_dict(
                        state_dict,
                        strict=False)
        self.weigth_loaded = True

    @torch_imported
    def load_voice(self, voice_label: str) -> TypeTensor:
        assert self.torch
        if voice_label in self.voices:
            return self.voices[voice_label]
        voice_weight = SpeechVoiceAsset(self.app, self.repo).load(voice_label)
        if self.device:
            self.voices[voice_label] = voice_weight.to(self.device)
        else:
            raise RuntimeError(
            "Attempting to load voice tensor before specifying a target device"
            )
        return self.voices[voice_label]

    @property
    def cuda_support(self) -> CudaSupport:
        assert self.torch
        available = self.torch.cuda.is_available()
        supported = False
        if available:
            major, minor = self.torch.cuda.get_device_capability()
            supported = f"sm_{major}{minor}" in self.torch.cuda.get_arch_list()
        return CudaSupport(available=available, supported=supported)

    @torch_imported
    def resolve_device_label(self, device) -> Literal["cpu", "mps", "cuda"]:
        assert self.torch

        if device == "cpu":
            return "cpu"

        if device not in ["cuda", "mps", "auto"]:
            raise RuntimeError(f"Unknown device type: {device}")

        cuda = self.cuda_support
        match device:
            case "cuda":
                if not cuda.available:
                    raise RuntimeError("CUDA requested but not available")
                elif not cuda.supported:
                    raise RuntimeError("GPU unsupported by this PyTorch build")
            case "mps":
                if not self.torch.backends.mps.is_available():
                    raise RuntimeError("MPS requested but not available")
            case "auto":
                device = "cpu"
                if cuda.available:
                    if cuda.supported:
                        device = "cuda"
                    else:
                        sys.stderr.write(
                                "\nPfSpeak: "
                                "GPU unsupported by this PyTorch build\n"
                                )
                elif self.torch.backends.mps.is_available():
                    device = "mps"

        return device

    def raise_for_missing_weights(self):
        if not self.weigth_loaded:
            raise RuntimeError(
                    "Weights where never loaded. "
                    "Attempting to operate with randomly initialized weights.")

    def load_the_model_if_the_weights_are_missing(self):
        if not self.weigth_loaded:
            self.load_model()

    @architecture_initialized
    def __call__(self,
                 phonemes: str,
                 voice: str,
                 speed: float
                 ) -> tuple[TypeTensor, TypeTensor]:
        """
        RETURNS A TUPLE OF TWO PYTORCH TENSORS.

        member 0:
            audio waveform.

        member 1:
            prediction_duration.

            This tells you how many frames each input phoneme should
            live for.

            Example:

                [3, 4, 5, 4]

            means the first phoneme lasts for 3 frames, the second
            lasts for 4, the third lasts for 5, and the fourth lasts
            for 4.

            You can think of it like:

                [000,1111,22222,3333]

            where each number is the index of the phoneme repeated
            for the number of frames the model predicted.
        """

        assert self.arch  # Guaranteed by the decorator; helps type checkers.

        references_table = self.load_voice(voice)  # Collection of referencees.

        self.load_the_model_if_the_weights_are_missing()  # Lazy load if needed.

        self.to_inference_mode()  # Calls eval(); disables training behavior.

        selected_by_phoneme_length = len(phonemes) - 1

        references = references_table[selected_by_phoneme_length]

        return self.arch(phonemes, references, speed)
