from collections.abc import Generator
import os
import json
import uuid
import socket
from time import sleep
from pathlib import Path
from threading import Thread
from multiprocessing import Queue
from abc import ABC, abstractmethod
from typing import Callable, Iterable

from pfspeak.common.dataclasses import (
        PfEvent,
        PfStatus,
        AudioChunk,
        WorkRequest,
        )
from pfspeak.extra.voices import VoiceEnum
from pfspeak.core.param import AudioChannels
from pfspeak.common.g2p import Graphemes2Phonemes
from pfspeak.common.requests import OllamaRequest
from pfspeak.core.session import SttBackend, TtsBackend
from pfspeak.common.types import AudioCallback, PathLike
from pfspeak.common.types import DifferedDef, VoidableDef


class StreamWorkers:
    def __init__(self, stream: InputStream) -> None:

        self.worker = self.__as_thread(stream.worker, stream)
        self.monitor = self.__as_thread(stream.monitor, stream)

    def __as_thread(self, job, stream: InputStream):
        def with_exception_handling():
            try:
                    job() 
            except Exception as exc:
                if stream.exceptions is None:
                    raise
                assert stream.exceptions
                stream.exceptions.put(exc)

        return Thread(target=with_exception_handling, daemon=True)

    def start(self):
        self.worker.start()
        self.monitor.start()

    def join(self):
        self.worker.join()
        self.monitor.join()


class InputStream(ABC):

    BACKEND: type[TtsBackend] | type[SttBackend]

    def __init__(self, callback: DifferedDef = None) -> None:
        super().__init__()

        self.device_id = uuid.uuid4()
        self.status = PfStatus()
        self._streaming = False

        self.request: Queue[str] = Queue()
        self.workers = StreamWorkers(self)
        self.callback: DifferedDef = callback
        self.exceptions: Queue | None = None

        self._current: PfEvent | None = None

    @property
    def streaming(self):
        return self._streaming

    @streaming.setter
    def streaming(self, value):
        self._streaming = value

    @property
    def current(self) -> PfEvent | None:
        return self._current

    @abstractmethod
    def worker(self): ...

    @abstractmethod
    def monitor(self): ...

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


class EndOfResponse: ...
EOF = EndOfResponse()

class TTSStream(InputStream):

    BACKEND = TtsBackend

    def __init__(self,
                 voice: VoiceEnum | str | None,
                 speed: float = 1,
                 callback: DifferableTTS= None,
                 g2p_bakend: Graphemes2Phonemes | None = None,
                 ) -> None:
        super().__init__(callback)
        self.voice = voice
        self.speed = speed
        self._text_buffer = ""
        self.g2p = g2p_bakend or Graphemes2Phonemes()
        self.last = ""

    def monitor(self):
        assert self.callback
        while self.streaming:
            line: str = self.request.get()
            self.last = line
            assert self.voice
            assert line, line
            self.callback(
                    WorkRequest(
                        device_id=self.device_id,
                        tokens=self.g2p(line),
                        voice=self.voice,
                        speed=self.speed
                        )
                    )

    def chunk(self, file: Iterable[str|EndOfResponse]):
        min_send_length = 1_024
        buffer = ""
        for line in file:
            print(f"'{line}'")

            if line is EOF:
                if buffer:
                    self.request.put(buffer)
                    buffer = ""
                continue

            assert isinstance(line, str)
            buffer += line
            if len(buffer) > min_send_length:
                print("Ollama: working on batch - length:", len(buffer))
                self.request.put(buffer)
                buffer = ""

    def worker(self):
        self.chunk(self.as_file())

    @abstractmethod
    def as_file(self) -> Iterable[str|EndOfResponse]: ...


class Hook(TTSStream):
    def __init__(self,
                 speed: float = 1,
                 voice: VoiceEnum | str | None = None,
                 callback: DifferableTTS = None,
                 g2p_bakend: Graphemes2Phonemes | None = None
                 ) -> None:
        super().__init__(voice, speed, callback, g2p_bakend)

    def adapter(self, text):
        self.request.put(text)

    def as_file(self):
        while True:
            yield self.request.get()


TTSCallback = Callable[[str, str, int], WorkRequest]
DifferableTTS = TTSCallback | None


class Ollama(TTSStream):
    def __init__(self,
                 model: str,
                 voice: VoiceEnum | str | None = None,
                 speed: float = 1,
                 callback: DifferableTTS = None,
                 g2p_bakend: Graphemes2Phonemes | None = None
                 ) -> None:
        super().__init__(voice, speed, callback, g2p_bakend)
        self.model = model
        self.prompts: Queue[tuple[str, str]] = Queue()

    def adapter(self,
                event: PfEvent | None = None,
                model: str | None = None,
                prompt: str | None = None,
                voice: VoiceEnum | str | None = None,
                speed: float | None = None
                ):
        if voice:
            self.voice = voice
        if speed:
            self.speed = speed
        if event and event.recording:
            prompt = event.recording.text
        elif event:
            raise ValueError
        elif prompt is None:
            raise ValueError("Ollama adapter requires a prompt or PfEvent")
        assert prompt is not None
        model = model or self.model
        self.prompts.put((model, prompt))

    def as_file(self) -> Generator[str|EndOfResponse]:
        print("ollama running")
        while True:
            model, prompt = self.prompts.get()
            model = model or self.model
            resp = OllamaRequest(model=model, stream=True).request(prompt)
            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                if text := json.loads(line).get("response"):
                    yield text
            yield EOF



class Fifo(TTSStream):
    def __init__(self,
                 path: PathLike,
                 voice: VoiceEnum | str | None = None,
                 speed: float = 1,
                 callback: DifferableTTS = None,
                 g2p_bakend: Graphemes2Phonemes | None = None
                 ) -> None:
        super().__init__(voice, speed, callback, g2p_bakend)
        self.path = Path(path)
        self.callback: VoidableDef = callback 

    def as_file(self) -> Generator[str|EndOfResponse]:
        if not self.path.exists():
            os.mkfifo(self.path)
        fd = os.open(self.path, os.O_RDONLY | os.O_NONBLOCK)
        with open(fd, "r") as fifo:
            while True:
                for line in fifo:
                    yield line
                yield EOF


class Tcp(TTSStream):
    def __init__(self,
                 port=8877,
                 host="127.0.0.1",
                 speed: float = 1,
                 callback: DifferableTTS = None,
                 voice: VoiceEnum | str | None = None,
                 g2p_bakend: Graphemes2Phonemes | None = None
                 ) -> None:
        super().__init__(voice, speed, callback, g2p_bakend)
        self.host = host
        self.port = port
        self.callback=callback

    def as_file(self) -> Generator[str | EndOfResponse]:
        with socket.socket() as server:
            conn, _ = server.accept()
            with conn:
                while self.streaming:
                    file = conn.makefile()
                    for line in file:
                        yield line
                    yield EOF


class STTStream(InputStream):

    BACKEND = SttBackend

    def __init__(self,
                 voice: VoiceEnum | str | None = None,
                 speed: float = 1,
                 callback: DifferedDef = None,
                 ) -> None:
        super().__init__(callback=callback)
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
        super().__init__(voice=voice, speed=speed)
        self.channels=channels
        self.device = device or default_input()
        self.samplerate = samplerate or default_samplerate(self.device)
        self.blocksize = blocksize or self.samplerate // 33

        self.stream = None
        self.status: PfStatus = PfStatus()
        self.callback: DifferedDef = callback

    def monitor(self):
        # A feature may one day live here.
        while self.streaming:
            sleep(.5)

    def worker(self):
        with self.__with_stream():
            assert self.stream
            while self.streaming:
                sleep(.5)

    def __with_stream(self):
        def wrapper(indata, *_):

            def mono(indata):
                if indata.shape[1] == 1:
                    return indata[:, 0].copy()
                else:
                    return indata.mean(axis=1)

            assert self.callback
            audio_chunk = AudioChunk(
                    waveform=mono(indata),
                    device_id=self.device_id,
                    samplerate=self.samplerate)

            if self.samplerate != 16_000:
                self.callback(audio_chunk.resample(16_000))
            else:
                self.callback(audio_chunk)

        import sounddevice as sd
        self.stream = sd.InputStream(
                device=self.device,
                samplerate=self.samplerate,
                blocksize=self.blocksize,
                channels=self.channels,
                callback=wrapper,
                dtype="float32",
                )

        return self.stream

    def __repr__(self):
        return (
                "Microphone:\n"
                f"  initialized     {self.stream is not None}\n"
                f"  samplerate      {self.samplerate}\n"
                f"  blocksize       {self.blocksize}\n"
                f"  channels        {self.channels}\n"
                f"  device          {self.device}"
                )

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


