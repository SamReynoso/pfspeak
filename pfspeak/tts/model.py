from functools import wraps
from pathlib import Path
import sys
from typing import Any, Dict, Literal

from pfspeak.tts.specs import ModelParams

from pfspeak.common.just_checking import (
        TypeArchitecture,
        NDArray,
        Float32,
        TypeTensor
        )
from pfspeak.common.dataclasses import Output
from dataclasses import dataclass
from types import ModuleType


def architecture_initialized(fn):
    @wraps(fn)
    def wrapper(self, *args, **kwargs):
        if self.arch is None:
            if self.params is None:
                raise RuntimeError(
                        "Attemting to initiate Architecture without module "
                        "parameters"
                        )
            from pfspeak.tts.architecture import KokoroArchitecture
            import torch
            self.arch = KokoroArchitecture(self.params)
            self.torch = torch
        return fn(self, *args, **kwargs)
    return wrapper

def torch_imported(fn):
    @wraps(fn)
    def wrapper(self, *args, **kwargs):
        if self.torch is None:
            import torch
            self.torch = torch
        return fn(self, *args, **kwargs)
    return wrapper

@dataclass(frozen=True)
class CudaSupport:
    available: bool
    supported: bool

class SpeechModel:
    def __init__(self, paramaters: ModelParams | None = None):
        self.params = paramaters
        self.device: Literal["cpu", "cuda", "mps"] | None = None
        self.arch: TypeArchitecture | None = None
        self.torch: ModuleType | None = None
        self.weigth_loaded: bool = False
        self.voices: Dict[Path, TypeTensor] = {}

    def with_params(self, params: ModelParams):
        self.params = params


    @architecture_initialized
    def to_device(self, device: str | None = None):
        self.raise_for_missing_weights()
        assert self.arch and self.params
        try:
            device = device or self.params.device
            self.device = self.resolve_device_label(device)
            self.arch.to(self.device)
            return self
        except RuntimeError as e:
            # TODO: Create an exception for this.
            raise e from e

    @architecture_initialized
    def to_inference_mode(self):
        self.raise_for_missing_weights()
        assert self.arch
        return self.arch.eval()

    @architecture_initialized
    def load_weights(self,
                     weights_file: Path | None = None,
                     map_location: str | None = None,
                     ):
        if weights_file is None:
            assert self.params
            weights_file = self.params.weights_file

        if map_location is None:
            assert self.params
            map_location = self.params.map_location

        assert self.torch
        loaded = self.torch.load(weights_file,
                                 map_location=map_location,
                                 weights_only=True)

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
    def load_voice(self, voice_path: Path) -> TypeTensor:
        assert self.torch
        if voice_path in self.voices:
            return self.voices[voice_path]
        voice = self.torch.load(voice_path, weights_only=True)
        if self.device:
            self.voices[voice_path] = voice.to(self.device)
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
