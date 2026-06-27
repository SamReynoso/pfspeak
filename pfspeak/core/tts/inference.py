import sys
from pathlib import Path
from types import ModuleType
from pfspeak.common.just_checking import (
        TypeArchitecture,
        NDArray,
        Float32,
        TypeTensor
        )
from pfspeak.core.params import SpeechParams
from pfspeak.common.dataclasses import Output
from typing import Any, Callable, Dict, Literal
from pfspeak.common.dataclasses import CudaSupport
from pfspeak.extra.decorators import architecture_initialized, torch_imported


WeightsLoader = Callable[..., Any]
VoiceFinder = Callable[[str], Path]
ParamLoader = Callable[..., SpeechParams]


class SpeechModel:
    def __init__(self,
                 params_loader: ParamLoader,
                 voice_finder: VoiceFinder,
                 weights_loader: WeightsLoader,
                 ) -> None:
        self.params = params_loader()

        self.voice_finder = voice_finder
        self.weights_loader = weights_loader
        self.loaded: bool = False

        self.torch: ModuleType | None = None
        self.arch: TypeArchitecture | None = None
        self.voices: Dict[Path, TypeTensor] = {}
        self.device: Literal["cpu", "cuda", "mps"] | None = None

    def load_model(self) -> None:
        self.load_weights()
        self.to_device()
        self.to_inference_mode()

    @architecture_initialized
    def to_device(self, device: str | None = None):
        self.raise_for_missing_weights()
        assert self.arch and self.params
        device = device or self.params.device
        self.device = self.resolve_device_label(device)
        self.arch.to(self.device)
        return self

    @architecture_initialized
    def to_inference_mode(self):
        self.raise_for_missing_weights()
        assert self.arch
        return self.arch.eval()

    @architecture_initialized
    def load_weights(self) -> None:
        assert self.params and self.torch
        loaded =  self.weights_loader(self.torch, "cpu")
        for key, state_dict in loaded.items():
            assert hasattr(self.arch, key), key
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
        voice_path = self.voice_finder(voice_label)
        if voice_path in self.voices:
            return self.voices[voice_path]
        voice_weight = self.torch.load(voice_path, weights_only=True)
        if self.device:
            self.voices[voice_path] = voice_weight.to(self.device)
        else:
            raise RuntimeError(
            "Attempting to load voice tensor before specifying a target device"
            )
        return self.voices[voice_path]

    @staticmethod
    def cast_waveform(output: Output) -> NDArray[Float32]:
        from numpy import array, float32
        return array(output.audio).astype(float32)

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

    @architecture_initialized
    def __call__(self, *args: Any, **kwds: Any) -> Any:
        self.raise_for_missing_weights()
        assert self.arch
        self.to_inference_mode()
        return self.arch.__call__(*args, **kwds)
