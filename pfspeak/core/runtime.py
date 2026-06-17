
import os
import json
from pathlib import Path
from multiprocessing import Pipe, Process

from huggingface_hub import hf_hub_download

from pfspeak.core.defaults import DEFAULT_APP_SPEC, Voices
from pfspeak.core.pipeline import PfPipeline
from pfspeak.core.specs import (
        AppSpec,
        ModelSpec,
        RuntimeSpec,
        )
from pfspeak.core.dataclasses import PipelineCmds

from typing import Callable, Dict, Optional


type VoiceMap = Dict[str, str]


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


def resolve_optional_model_name(model: Optional[str]):
    match model:
        case None | "": return "kokoro-v1_0.pth"
        case "kokoro-v1_0": return model + ".pth"
        case "kokoro-v1_1-zh": return model + ".pth"
        case "kokoro-v1_0.pth": return model
        case "kokoro-v1_1-zh.pth": return model
        case "hexgrad/Kokoro-82M-v1.1-zh": return "kokoro-v1_1-zh.pth"
        case "hexgrad/Kokoro-82M": return "kokoro-v1_0.pth"
        case _: raise RuntimeError("This model name could not be resolved")


class Runtime:
    voice_paths: VoiceMap = dict()

    def __init__(self,
                 app_spec: AppSpec | None = None,
                 runtime_spec: RuntimeSpec | None = None,
                 ) -> None:

        self._conn = None
        self.register = CallableRegister()

        if app_spec is None:
            self.app_spec = DEFAULT_APP_SPEC
        else:
            self.app_spec = app_spec 

        if runtime_spec is None:
            self.runtime_spec = RuntimeSpec()
        else:
            self.runtime_spec = runtime_spec

        # TODO: Add fallback rules
        self.resolve_device_name()

        self.pipeline = PfPipeline(self.runtime_spec)

    def resolve_device_name(self):
        if self.runtime_spec.device == "auto":
            self.runtime_spec.device = "cpu"

    def prepare(self,
                voices: list[str | Voices] | None = None,
                voice: Optional[str | Voices] = None,
                model: Optional[str] = None
                ):

        def dl_voice(voice: str | Voices):
            voice_filename = f"voices/{str(voice)}.pt" 
            if not (self.app_spec.data_dir / voice_filename).exists():
                self.download(voice_filename)

        if voice: dl_voice(voice)

        if voices:
            for voice in voices: dl_voice(voice)

        model_filename = resolve_optional_model_name(model)
        if not (self.app_spec.data_dir / model_filename).exists():
            self.download(model_filename)
    

    def get_model_config(self,
                         model_path: Optional[str | Path] = None,
                         model_label: Optional[str] = None,
                         ) -> ModelSpec:

        def resolve_model_path(model_path, model_label) -> Path:
            if model_path and model_label:
                raise RuntimeError
            if model_path:
                if isinstance(model_path, str):
                    model_path = Path(model_path)
            elif self.runtime_spec.model_path:
                model_path = self.runtime_spec.model_path
            else:
                filename = resolve_optional_model_name(model_label)
                model_path = self.app_spec.data_dir / filename
            if not model_path.exists():
                raise RuntimeError()
            return model_path

        model_path=resolve_model_path(model_path, model_label)

        def resolve_config_path() -> Path:
            if self.runtime_spec.config_path:
                config_file = self.runtime_spec.config_path
            else:
                config_file = self.app_spec.data_dir / "kokoro.json"
            return config_file

        config_target = resolve_config_path()
        if config_target.exists():
            return ModelSpec(
                    model_path=model_path,
                    disable_complex=self.runtime_spec.disable_complex,
                    map_location=self.runtime_spec.map_location,
                    weights_only=self.runtime_spec.weights_only,
                    device=self.runtime_spec.device,
                    **json.loads(
                        config_target.read_text()
                                 )
                             )
        elif self.runtime_spec.local_only:
            raise RuntimeError
        else:
            config_file = self.download("config.json")
            config_file.replace(config_target)
            return ModelSpec(
                    model_path=model_path,
                    **json.loads(
                        config_file.read_text()
                        )
                    )

    def download(self, filename: str) -> Path:
        def resolve_hf_token() -> str | bool:
            if token := os.getenv("HF_TOKEN"):
                return token
            else:
                return False

        return Path(
                hf_hub_download(
                    self.runtime_spec.model_id,
                    filename,
                    cache_dir=self.app_spec.cache_dir,
                    local_dir=self.app_spec.data_dir,
                    token=resolve_hf_token(),
                    )
                )

    def resolve_voice_path(self, voice_label: str):
        voice_filename = f"voices/{voice_label}.pt"
        voice_path = self.app_spec.data_dir / voice_filename
        if not voice_path.exists():
            # TODO: Only if you can down load now.
            returned_path = self.download(voice_filename)
            assert voice_path == returned_path
        return voice_path

    def speak(self, text: str, voice: str, speed: Optional[float] = None):
        voice_path = self.resolve_voice_path(voice)
        assert self.pipeline 
        self.pipeline.en_callable = self.register.en_callable
        self.pipeline.speed = self.register.speed
        if not self.pipeline.model_loaded:
            self.pipeline.load_model(self.get_model_config())
        return self.pipeline(
                PipelineCmds(
                    op="speak",
                    text=text,
                    voice=voice_path,
                    speed=speed,
                    )
                )

    def start(self):
        parent, child = Pipe()
        self._conn = parent
        self._worker_process = Process(target=self.worker,
                                       args=(
                                           self.pipeline,
                                           self.get_model_config(),
                                           child,
                                             )
                                       )
        self._worker_process.start()

    @staticmethod
    def worker(pipeline: PfPipeline, model_spec: ModelSpec, conn):
        pipeline.load_model(model_spec)
        pipeline.run_forever(conn)

    def speak_async(self, text: str, voice: str, speed: Optional[float] = None):
        voice_path = self.resolve_voice_path(voice)
        assert self.pipeline and self._conn
        self.pipeline.en_callable = self.register.en_callable
        self.pipeline.speed = self.register.speed
        self.pipeline.send(
                self._conn,
                PipelineCmds(
                    op="speak",
                    text=text,
                    voice=voice_path,
                    speed=speed,
                    )
                )

    def close(self):
        assert self._conn
        self._conn.send(PipelineCmds(op="stop"))
        self._worker_process.join()

    def recv(self):
        assert self._conn
        return self._conn.recv()
