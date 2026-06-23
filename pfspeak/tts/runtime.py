import json
from pathlib import Path

from pfspeak.common import models
from pfspeak.common.defaults import (
        DEFAULT_APP_SPEC,
        AppSpec,
        Voices
        )
from pfspeak.tts.pipeline import PfPipeline

from typing import Callable, Optional

from pfspeak.tts.specs import G2PSpec, ModelParams, SpeechSpec


class CallableRegister:

    def __init__(self) -> None:
        self._en_callable = None
        self._speed= None

    @property
    def en_callable(self):
        return self._en_callable

    def set_en_callable(self, fn: Callable | None):
        if fn is not None:
            self._en_callable = fn
            return fn
        def decorator(fn: Callable):
            self._en_callable = fn
            return fn
        return decorator

    @property
    def speed(self):
        return self._speed

    def set_speed(self, fn: Callable | None):
        if fn is not None:
            self._speed = fn
            return fn
        def decorator(fn: Callable):
            self._speed = fn
            return fn
        return decorator


def resolve_weights_filename(a_string: Optional[str]) -> str:
    match a_string:
        case None | "":
            return "kokoro-v1_0.pth"
        case "kokoro-v1_0.pth":
            return a_string
        case "kokoro-v1_1-zh.pth":
            return a_string
        case "kokoro-v1_0":
            return a_string + ".pth"
        case "kokoro-v1_1-zh":
            return a_string + ".pth"
        case "hexgrad/Kokoro-82M-v1.1-zh":
            return "kokoro-v1_1-zh.pth"
        case "hexgrad/Kokoro-82M":
            return "kokoro-v1_0.pth"
        case _:
            raise RuntimeError(
                f"Error: '{a_string}' could not be resolved to a weights file"
                )

def start_on_call(fn: Callable):
    def decorator(self, *args, **kwargs):
        if not self._pipeline_started:
            self.pipeline.start(self.model_params, self.g2p_kwargs)
            self._pipeline_started = True
        return fn(self, *args, **kwargs)
    return decorator


class TextToSpeech:

    def __init__(self,
                 app_spec: AppSpec | None = None,
                 runtime_spec: SpeechSpec | None = None,
                 g2p_spec: G2PSpec | None = None,
                 ) -> None:


        self.app_spec = app_spec or DEFAULT_APP_SPEC
        self.runtime_spec = runtime_spec or SpeechSpec()
        self.g2p_spec = g2p_spec or G2PSpec()

        self.register = CallableRegister()
        self.pipeline = PfPipeline()
        self.download = models.install_model(self.app_spec, self.runtime_spec)
        self._pipeline_started = False

    @property
    def local_dir(self) -> Path:
        return self.runtime_spec.resolv_local_dir(self.app_spec)

    @property
    def weights_filename(self) -> str:
        return resolve_weights_filename(self.runtime_spec.model_id)

    @property
    def weights_path(self) -> Path:
        return self.local_dir / self.weights_filename

    @property
    def source_params_filename(self) -> str:
        return "config.json"

    @property
    def params_path(self) -> Path:
        return self.local_dir / "params.json"

    def prepare_weights(self):
        if not self.weights_path.exists():
            self.download(self.weights_filename)

    def prepare_params(self):
        if not self.params_path.exists():
            file = self.download(self.source_params_filename)
            file.rename(self.params_path)

    def voice_weights_filename(self, voice_label: str) -> str:
        return f"voices/{voice_label}.pt"

    def voice_weights_path(self, voice_label: str) -> Path:
        return self.local_dir / self.voice_weights_filename(voice_label)

    def prepare_voice(self, label: str):
        if not self.voice_weights_path(label).exists():
            self.download(self.voice_weights_filename(label))

    def prepare_voices(self, labels: list[str | Voices]):
        for voice in labels:
            self.prepare_voice(voice)

    def resolv_speed(self, text, provided: float | None) -> float:
        if provided:
            return provided
        elif self.register.speed:
            return self.register.speed(text)
        return 1

    @property
    def model_params(self) -> ModelParams:
        return ModelParams(
                weights_file=self.weights_path,
                **json.loads(self.params_path.read_text())
                )

    def speak_kwargs(self, text: str, voice: str, speed: float | None = None):
        return {
                'text': text,
                "voice": self.voice_weights_path(voice),
                "speed": self.resolv_speed(text, speed)
                }

    @property
    def g2p_kwargs(self):
        return {
                "spec": self.g2p_spec,
                "en_callable": self.register.en_callable,
                }
        
    @start_on_call
    def speak(self, text: str, voice: str, speed: float | None = None):
        return self.pipeline(**self.speak_kwargs(text, voice, speed))

    def start_pipeline(self, params, g2p_parms):
        self.pipeline.start(params, g2p_parms)

    def start_worker(self, params, g2p_parmas):
        self.pipeline.start_worker(params, g2p_parmas)

    def speak_async(self, text: str, voice: str, speed: Optional[float] = None):
        return self.pipeline.send(**self.speak_kwargs(text, voice, speed))

    def recv(self):
        return self.pipeline.recv()

    def close(self):
        self.pipeline.stop()

