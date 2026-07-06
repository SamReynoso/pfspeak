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
            job() 
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
        self.jobs = Queue()
        self.status = PfStatus()
        self.__uuid = uuid.uuid4()
        self.workers = StreamWorkers(self)
        self.exceptions: DifferedDef = None
        self._current: PfEvent | None = None
        self.callback: DifferedDef = callback
        self._streaming = False

    @property
    def streaming(self):
        return self._streaming

    @streaming.setter
    def streaming(self, value):
        self._streaming = value

    @property
    def active(self):
        return (
                self.workers.worker.is_alive()
                and
                self.workers.monitor.is_alive()
                )

    @property
    def device_id(self):
        return self.__uuid

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
            line: str = self.jobs.get()
            self.last = line
            line = " ".join(line.splitlines())
            self.callback(
                    WorkRequest(
                        device_id=self.device_id,
                        tokens=self.g2p(line),
                        voice=self.voice,
                        speed=self.speed
                        )
                    )

    def run(self, file: Iterable[str]):
        min_send_length = 1_024
        buffer = ""
        for line in file:
            buffer += line
            if len(buffer) > min_send_length:
                self.jobs.put(buffer)
            self.jobs.put(buffer)

    def worker(self):
        self.run(self.as_file())

    @abstractmethod
    def as_file(self) -> Iterable[str]: ...


class Hook(TTSStream):
    def __init__(self,
                 speed: float = 1,
                 voice: VoiceEnum | str | None = None,
                 callback: DifferableTTS = None,
                 g2p_bakend: Graphemes2Phonemes | None = None
                 ) -> None:
        super().__init__(voice, speed, callback, g2p_bakend)

    def adapter(self, text):
        self.jobs.put(text)

    def as_file(self):
        while True:
            yield self.jobs.get()


TTSCallback = Callable[[str, str, int], WorkRequest]
DifferableTTS = TTSCallback | None


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

    def as_file(self):
        if not self.path.exists():
            os.mkfifo(self.path)
        fd = os.open(self.path, os.O_RDONLY | os.O_NONBLOCK)
        with open(fd, "r") as fifo:
            while True:
                for line in fifo:
                    yield line


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
        self._prompt: Queue[str] = Queue()

    def adapter(self,
                event: PfEvent | None = None,
                model: str | None = None,
                prompt: str | None = None
                ):
        if event:
            if event.recording:
                prompt = event.recording.text
        elif prompt is None:
            raise ValueError("Ollama adapter requires a prompt or PfEvent")
        model = model or self.model
        self.jobs.put((model, prompt))

    def as_file(self):
        print("ollama running")
        while True:
            model, prompt = self.jobs.get()
            model = model or self.model
            resp = OllamaRequest(model=model, stream=True).request(prompt)
            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                if text := json.loads(line).get("response"):
                    yield text

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

    def as_file(self):
        with socket.socket() as server:
            conn, _ = server.accept()
            with conn:
                while self.streaming:
                    file = conn.makefile()
                    for line in file:
                        yield line


class STTStream(InputStream):

    BACKEND = SttBackend



class Microphone(STTStream):

    def __init__(self,
                 blocksize: int = 1_000,
                 samplerate: int = 16_000,
                 device: int | str | None = None,
                 callback: AudioCallback | None = None,
                 channels: AudioChannels | int = AudioChannels.MONO,
                 ) -> None:
        super().__init__()
        self.stream = None
        self.device = device
        self.channels=channels
        self.blocksize = blocksize
        self.samplerate = samplerate
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
        def wrapper(indata, frames, time, _):
            del frames

            def mono(indata):
                if indata.shape[1] == 1:
                    return indata[:, 0].copy()
                else:
                    return indata.mean(axis=1)

            assert self.callback
            self.callback(
                    AudioChunk(
                        waveform=mono(indata),
                        device_id=self.device_id,
                        samplerate=self.samplerate,
                        start_time=time.inputBufferAdcTime
                        )
                    )

        import sounddevice as sd
        self.stream = sd.InputStream(
                samplerate=self.samplerate,
                blocksize=self.blocksize,
                channels=self.channels,
                device=self.device,
                callback=wrapper,
                dtype="float32",
                )

        return self.stream

    def __repr__(self):
        import sounddevice as sd
        return (
                "Microphone:\n"
                f"  default device  {sd.default.device}\n"
                f"  initualized     {self.stream is not None}\n"
                f"  samplerate      {self.samplerate}\n"
                f"  blocksize       {self.blocksize}\n"
                f"  channels        {self.channels}\n"
                f"  device          {self.device}"
                )


class Devices:
    Tcp = Tcp
    Fifo = Fifo
    Ollama = Ollama
    Microphone = Microphone
