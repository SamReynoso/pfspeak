
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


def resolve_optional_model_name(model_label: Optional[str]):
    match model_label:
        case None | "": return "kokoro-v1_0.pth"
        case "kokoro-v1_0": return model_label + ".pth"
        case "kokoro-v1_1-zh": return model_label + ".pth"
        case "kokoro-v1_0.pth": return model_label
        case "kokoro-v1_1-zh.pth": return model_label
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

        if not app_spec: self.app_spec = DEFAULT_APP_SPEC
        else: self.app_spec = app_spec 
        if not runtime_spec: self.runtime_spec = RuntimeSpec()
        else: self.runtime_spec = runtime_spec

        if True:
            self.resolve_device_name()
            self.prepare()

        self.pipeline = PfPipeline(self.runtime_spec)

    def prepare(self,
                voice_label: Optional[str | Voices] = None,
                voice_labels: list[str | Voices] | None = None,
                model_label: Optional[str] = None
                ):

        def dl_voice(voice: str | Voices):
            voice_filename = f"voices/{str(voice)}.pt" 
            if not (self.app_spec.data_dir / voice_filename).exists():
                self.download(voice_filename)

        def dl_model(model_label: str):
            if not (self.app_spec.data_dir / model_label).exists():
                self.download(model_label)

        def dl_model_params(param_path: Path):
            if not param_path.exists():
                file_path = self.download("config.json")
                file_path.rename(param_path)

        if voice_label: dl_voice(voice_label)

        if voice_labels:
            for voice in voice_labels: dl_voice(voice)

        model_label = resolve_optional_model_name(model_label)
        dl_model(model_label)
        model_params_path = self.app_spec.data_dir / "model_params.json"
        dl_model_params(model_params_path)


    def resolve_voice_weights(self, voice_label: str):
        voice_filename = f"voices/{voice_label}.pt"
        voice_path = self.app_spec.data_dir / voice_filename
        if not voice_path.exists():
            returned_path = self.download(voice_filename)
            assert voice_path == returned_path
        return voice_path

    def resolve_device_name(self):
        if self.runtime_spec.device == "auto":
            self.runtime_spec.device = "cpu"

    def get_model_config(self,
                         model_path: Optional[str | Path] = None,
                         model_label: Optional[str] = None,
                         ) -> ModelSpec:

        def resolve_model_weights(model_path, model_label) -> Path:
            if model_path and model_label:
                raise RuntimeError(
                        "Path and Label can not both be used when resolving "
                        "the model path"
                        )
            if model_path:
                model_path = Path(model_path)
            elif self.runtime_spec.model_path:
                model_path = self.runtime_spec.model_path
            else:
                filename = resolve_optional_model_name(model_label)
                model_path = self.app_spec.data_dir / filename
            if not model_path.exists():
                self.prepare(model_label=model_label)
            return model_path

        def resolve_model_params():
            self.prepare()
            return self.app_spec.data_dir / "model_params.json"


        model_weights=resolve_model_weights(model_path, model_label)
        model_params = resolve_model_params()

        return ModelSpec(
                model_path=model_weights,
                disable_complex=self.runtime_spec.disable_complex,
                map_location=self.runtime_spec.map_location,
                weights_only=self.runtime_spec.weights_only,
                device=self.runtime_spec.device,
                **json.loads(
                    model_params.read_text()
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

    def speak(self, text: str, voice: str, speed: Optional[float] = None):
        voice_path = self.resolve_voice_weights(voice)
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
        voice_path = self.resolve_voice_weights(voice)
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
