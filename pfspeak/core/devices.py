import os
import json
import uuid
import socket
from time import sleep
from queue import Queue
from pathlib import Path
from typing import Iterable
from threading import Thread
from abc import ABC, abstractmethod
from collections.abc import Generator
from pfspeak.common.dataclasses import (
        PfEvent,
        PfStatus,
        AudioChunk,
        Sentinel,
        WorkRequest)
from pfspeak.core.types import ServiceTypes
from pfspeak.extra.voices import VoiceEnum
from pfspeak.core.param import AudioChannels
from pfspeak.common.defaults import SENTINEL
from pfspeak.common.types import DeferrableDef
from pfspeak.common.g2p import Graphemes2Phonemes
from pfspeak.common.requests import OllamaRequest
from pfspeak.common.types import AudioCallback, PathLike


class StreamWorkers:
    def __init__(self, stream: InputStream) -> None:

        self.worker = self.__as_thread(stream.worker, stream)
        self.monitor = self.__as_thread(stream.monitor, stream)
        self.wake_up = stream.wake_up

    def __as_thread(self, job, stream: InputStream):
        def with_exception_handling():
            try:
                    job() 
            except Exception as exc:
                if stream.submit_exceptions is None:
                    raise RuntimeError("Device exceptons queue is None")
                assert stream.submit_exceptions
                stream.submit_exceptions(exc)

        return Thread(target=with_exception_handling, daemon=True)

    def start(self):
        self.worker.start()
        self.monitor.start()

    def join(self):
        self.wake_up()
        self.worker.join()
        self.monitor.join()


class InputStream(ABC):

    def __init__(self, callback: DeferrableDef = None) -> None:
        super().__init__()

        self.device_id = uuid.uuid4()
        self.status = PfStatus()
        self.service: ServiceTypes

        self.request: Queue[str|Sentinel] = Queue()
        self.workers = StreamWorkers(self)
        self.callback: DeferrableDef = callback
        self.submit_exceptions: DeferrableDef = None

        self._active: PfEvent | None = None

        self._streaming = False

    @property
    def streaming(self):
        return self._streaming

    @streaming.setter
    def streaming(self, value):
        self._streaming = value

    @property
    def active(self) -> PfEvent | None:
        return self._active

    @active.setter
    def active(self, value: PfEvent | None) -> PfEvent | None:
        if value is None:
            pass
        if value is not None and value.recording is None:
            raise ValueError("Device active event must have a recording")
        self._active = value

    @abstractmethod
    def worker(self): ...

    @abstractmethod
    def monitor(self): ...

    @abstractmethod
    def wake_up(self): ...

    def start(self):
        self.streaming = True 
        self.workers.start()

    def stop(self):
        self.streaming = False
        self.workers.join()

    def __enter__(self):
        self.start()

    def __exit__(self):
        self.stop()


class EndOfResponse:
    def __repr__(self):
        return "END OF RESPONSE"


EOF = EndOfResponse()


class TTSStream(InputStream):

    def __init__(self,
                 voice: VoiceEnum | str | None,
                 speed: float = 1,
                 callback: DeferrableDef = None,
                 g2p_backend: Graphemes2Phonemes | None = None,
                 ) -> None:
        super().__init__(callback)
        self.service = ServiceTypes.TTS
        self.voice = voice
        self.speed = speed
        self.g2p = g2p_backend or Graphemes2Phonemes()
        self.last = ""

    def monitor(self):
        while self.streaming:

            line: str | Sentinel = self.request.get()

            if line is SENTINEL:
                break

            if self.voice is None:
                raise ValueError("Device missing voice at time of synthesis")

            assert isinstance(line, str)

            self.last = line
            assert line, line
            assert self.callback
            self.callback(
                    PfEvent(
                        device=self,
                        device_id=self.device_id,
                        recording=None,
                        finalized=False,
                        service=PfEvent.EventTypes.TTS,
                        request=WorkRequest(
                            device_id=self.device_id,
                            tokens=self.g2p(line),
                            voice=self.voice,
                            speed=self.speed)
                        )
                    )

    def chunk(self, file: Iterable[str|EndOfResponse|Sentinel]):
        min_send_length = 1_024
        buffer = ""
        for line in file:

            if line is SENTINEL:
                break

            if line is EOF:
                if buffer:
                    self.request.put(buffer)
                    buffer = ""
                continue

            assert isinstance(line, str)
            buffer += line
            if len(buffer) > min_send_length:
                # print(f"TTS: input batch length ({len(buffer)})")
                self.request.put(buffer)
                buffer = ""
        self.request.put(SENTINEL)

    def worker(self):
        self.chunk(self.as_file())

    @abstractmethod
    def as_file(self) -> Generator[str|EndOfResponse|Sentinel]: ...


class Ollama(TTSStream):
    def __init__(self,
                 model: str,
                 voice: VoiceEnum | str | None = None,
                 speed: float = 1,
                 callback: DeferrableDef = None,
                 g2p_backend: Graphemes2Phonemes | None = None
                 ) -> None:
        super().__init__(voice, speed, callback, g2p_backend)
        self.model = model
        self.prompts: Queue[tuple[str, str]|Sentinel] = Queue()

    def adapter(self,
                event: PfEvent | None = None,
                prompt: str | None = None,
                voice: VoiceEnum | str | None = None,
                speed: float | None = None,
                model: str | None = None,
                ):
        prompt = event.recording.text if event and event.recording else prompt
        if prompt is None:
            raise ValueError("Ollama adapter requires event or prompt")
        if voice:
            self.voice = voice
        if speed:
            self.speed = speed
        model = model or self.model
        self.prompts.put((model, prompt))

    def as_file(self) -> Generator[str|EndOfResponse|Sentinel]:
        print("ollama running")
        while self.streaming:
            value = self.prompts.get()
            if isinstance(value, Sentinel):
                break
            model = value[0] or self.model
            prompt = value[1]
            resp = OllamaRequest(model=model, stream=True).request(prompt)
            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                if text := json.loads(line).get("response"):
                    yield text
            yield EOF
        yield SENTINEL

    def wake_up(self):
        self.prompts.put(SENTINEL)


class Fifo(TTSStream):
    def __init__(self,
                 path: PathLike,
                 voice: VoiceEnum | str | None = None,
                 speed: float = 1,
                 callback: DeferrableDef = None,
                 g2p_backend: Graphemes2Phonemes | None = None,
                 exists_ok: bool = False,
                 ) -> None:
        super().__init__(voice, speed, callback, g2p_backend)
        self.path = Path(path)
        self.exists_ok = exists_ok

    def as_file(self) -> Generator[str|EndOfResponse|Sentinel]:
        if self.path.exists():
            if not self.exists_ok:
                raise RuntimeError("Attempting to create FIFO but path exists")
            created = False
        else:
            os.mkfifo(self.path)
            created = True
        try:
            with open(self.path, "r") as fifo:
                while self.streaming:
                    for line in fifo:
                        yield line
                    yield EOF
            print("Fifo: shutdown complete")
            yield SENTINEL
        finally:
            if created and self.path.exists():
                self.path.unlink()

    def wake_up(self) -> None:
        with open(self.path, "w"):
            return None


class Tcp(TTSStream):
    def __init__(self,
                 port: int =24024,
                 host: str ="127.0.0.1",
                 voice: VoiceEnum | str | None = None,
                 speed: float = 1,
                 callback: DeferrableDef = None,
                 g2p_backend: Graphemes2Phonemes | None = None
                 ) -> None:
        super().__init__(voice, speed, callback, g2p_backend)
        self.host = host
        self.port = port
        self.conn: socket.socket | None = None
        self.server: socket.socket | None = None

    def as_file(self) -> Generator[str|EndOfResponse|Sentinel]:
        with socket.socket() as server:
            self.server = server
            self.server.bind((self.host, self.port))
            self.conn, _ = server.accept()
            with self.conn:
                while self.streaming:
                    file = self.conn.makefile()
                    for line in file:
                        yield line
                    yield EOF
        yield SENTINEL

    def wake_up(self):
        if self.conn:
            self.conn.shutdown(socket.SHUT_RDWR)
            self.conn.close()

        if self.server:
            self.server.close()


class Hook(TTSStream):
    def __init__(self,
                 speed: float = 1,
                 voice: VoiceEnum | str | None = None,
                 callback: DeferrableDef = None,
                 g2p_backend: Graphemes2Phonemes | None = None
                 ) -> None:
        super().__init__(voice, speed, callback, g2p_backend)
        self.jobs: Queue[str|Sentinel] = Queue()

    def adapter(self, text: str) -> None:
        self.jobs.put(text)

    def as_file(self) -> Generator[str|EndOfResponse|Sentinel]:
        while self.streaming:
            yield self.jobs.get()
            yield EOF
        yield SENTINEL

    def wake_up(self) -> None:
        self.jobs.put(SENTINEL)


class STTStream(InputStream):

    def __init__(self,
                 voice: VoiceEnum | str | None = None,
                 speed: float = 1,
                 callback: DeferrableDef = None,
                 ) -> None:
        super().__init__(callback=callback)
        self.service = ServiceTypes.STT
        self.voice = voice
        self.speed = speed


class Microphone(STTStream):

    def __init__(self,
                 voice: VoiceEnum | str | None = None,
                 speed: float = 1,
                 blocksize: int | None = None,
                 samplerate: int | None = None,
                 device: int | str | None = None,
                 callback: AudioCallback | None = None,
                 channels: AudioChannels | int = AudioChannels.MONO
                 ) -> None:
        super().__init__(voice=voice, speed=speed, callback=callback)
        self.channels=channels
        self.device = device or default_input()
        self.samplerate = samplerate or default_samplerate(self.device)
        self.blocksize = blocksize or self.samplerate // 33

        self.stream = None
        self.status: PfStatus = PfStatus()

    def monitor(self):
        # A feature may one day live here.
        while self.streaming:
            sleep(.5)

    def worker(self):
        with self.__with_stream():
            while self.streaming:
                sleep(.5)

    def __with_stream(self):
        def mono(indata):
            if indata.shape[1] == 1:
                return indata[:, 0].copy()
            else:
                return indata.mean(axis=1).copy()

        def wrapper(indata, *_):

            audio_chunk = AudioChunk(
                    waveform=mono(indata),
                    device_id=self.device_id,
                    samplerate=self.samplerate)

            if self.samplerate != 16_000:
                audio_chunk = audio_chunk.resample(16_000)

            assert self.callback
            self.callback(audio_chunk)

        import sounddevice
        self.stream = sounddevice.InputStream(
                device=self.device,
                samplerate=self.samplerate,
                blocksize=self.blocksize,
                channels=self.channels,
                callback=wrapper,
                dtype="float32")

        return self.stream

    def __repr__(self):
        return ("Microphone:\n"
                f"  initialized     {self.stream is not None}\n"
                f"  samplerate      {self.samplerate}\n"
                f"  blocksize       {self.blocksize}\n"
                f"  channels        {self.channels}\n"
                f"  device          {self.device}")

    def stop(self):
        if self.stream and self.stream.active:
            self.stream.close()
        self.streaming = False
        self.workers.join()

    def wake_up(self): ...


def default_input():

    def on_device_name(candidate):
        return candidate[1]["name"]

    import sounddevice as sd
    candidates = []
    for i, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] == 0:
            continue
        name = dev["name"].lower()
        if name in {"default", "pulse", "pipewire", "jack", "oss"}:
            continue
        candidates.append((i, dev))

    candidates.sort(key=on_device_name)
    if not candidates:
        raise RuntimeError("No recording devices found.")

    if len(candidates) == 1:
        return candidates[0][0]

    default = sd.default.device[0]
    if any(i == default for i, _ in candidates):

        print("default device:", default)
        return default
    print("default device:", candidates[0][0])
    return candidates[0][0]


def default_samplerate(hardware_device):
    import sounddevice as sd
    info = sd.query_devices(hardware_device)
    print ("auto samplerate:", int(info["default_samplerate"]))
    return int(info["default_samplerate"])


class Devices:
    Tcp = Tcp
    Fifo = Fifo
    Ollama = Ollama
    Microphone = Microphone
