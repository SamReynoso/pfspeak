import os
import json
import sys
from time import time
import uuid
import socket
from pathlib import Path
from threading import Thread
from multiprocessing import Queue
from abc import ABC, abstractmethod
from pfspeak.extra.voices import VoiceEnum
from pfspeak.core.param import AudioChannels
from pfspeak.common.requests import OllamaRequest
from pfspeak.core.session import STTSession, TTSSession
from pfspeak.common.types import AudioCallback, PathLike
from pfspeak.common.types import DifferedDef, VoidableDef
from pfspeak.common.dataclasses import AudioChunk, PfEvent, TokenList, WorkRequest


class InputStream(ABC):

    SESSIONIZER: type[TTSSession] | type[STTSession]

    def __init__(self,
                 callback: DifferedDef = None,
                 voice: VoiceEnum | str | None = None,
                 speed: float = 1,
                 ) -> None:
        super().__init__()
        self.voice = voice
        self.speed = speed
        self.thread = None
        self.recordings = []
        self.streaming = False
        self.uuid = uuid.uuid4()
        self.exceptions: DifferedDef = None
        self._current: PfEvent | None = None
        self.callback: DifferedDef = callback

    @property
    def device_id(self):
        return self.uuid

    @property
    def current(self) -> PfEvent | None:
        return self._current

    @abstractmethod
    def run(self): ...

    def start(self):
        self.thread = Thread(target=self.run, daemon=True)
        self.streaming = True
        self.thread.start()

    def stop(self):
        self.streaming = False
        if self.thread:
            self.thread.join()


class TTSStream(InputStream):

    SESSIONIZER = TTSSession

    def request(self, text: str):
        req = WorkRequest(
                device_id=self.uuid,
                speed=self.speed,
                voice=self.voice,
                text=" ".join(text.splitlines()),
                )
        assert self.callback
        self.callback(req)
    

class STTStream(InputStream):

    SESSIONIZER = STTSession


class Ollama(TTSStream):
    def __init__(self,
                 model: str,
                 callback: AudioCallback | None = None
                 ) -> None:
        super().__init__()
        self.model = model
        self.jobs = Queue()
        self.callback = callback
        self.last = ""

    def ping(self, timeout: float = 10.0) -> bool:
        model = ""
        return OllamaRequest(model).ping(timeout)

    def pull(self, model: str) -> None:
        OllamaRequest(model=model).pull()

    def adaptor(self,
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

    def run(self):
        try:
            print("Device: Ollama online")
            while self.streaming:
                model, prompt = self.jobs.get()
                if model is False or prompt is False:
                    continue

                full = ""
                buffer = ""
                buffer_size  = 300
                request_start = time()
                resp = OllamaRequest(model=model, stream=True).request(prompt)
                gen = resp.iter_lines(decode_unicode=True)

                print(f"Ollama: {time() - request_start} seconds")

                for line in gen:

                    if not line:
                        continue
                    if not (text := json.loads(line).get("response")):
                        continue

                    candidate = buffer + text
                    if len(candidate) > buffer_size:
                        self.request(buffer)
                        print("======= buffer sent - buffer size:", len(buffer))
                        buffer = text
                    else:
                        buffer = candidate
                    full += text

                if buffer:
                    self.request(buffer)
                self.last = full
                sys.stderr.write(full + "\n>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n")

        except Exception as e:
            assert self.exceptions
            self.exceptions(e)

    def stop(self):
        self.streaming = False
        self.jobs.put((False, False))
        if self.thread:
            self.thread.join()

class Hook(TTSStream):
    def __init__(self, callback: VoidableDef = None) -> None:
        super().__init__()
        self.callback: VoidableDef = callback 

    def speak(self, line: str, voice: str, speed: float = 1.0):
        print("Hook: routing request to device session")
        self.voice = voice
        self.speed = speed
        assert self.callback
        self.request(line)

    def run(self):
        ...

class Fifo(TTSStream):
    def __init__(self, path: PathLike, callback: VoidableDef = None) -> None:
        super().__init__()
        self.path = Path(path)
        self.callback: VoidableDef = callback 
        self.streaming = False

    def run(self):
        try:
            assert self.callback
            if not self.path.exists():
                os.mkfifo(self.path)
            fd = os.open(self.path, os.O_RDONLY | os.O_NONBLOCK)
            print("Device: Fifo online")
            self.streaming = True
            with open(fd, "r") as fifo:
                while self.streaming:
                    for line in fifo:
                        self.request(line)
        except Exception as e:
            assert self.exceptions
            self.exceptions(e)


class Tcp(TTSStream):

    def __init__(self, host="127.0.0.1", port=8877, callback=None) -> None:
        super().__init__()
        self.host = host
        self.port = port
        self.callback=callback

    def run(self):
        try:
            assert self.callback
            with socket.socket() as server:
                conn, _ = server.accept()
                print("Device: Tcp online")
                while self.streaming:
                    with conn:
                        file = conn.makefile()

                        for line in file:
                            self.request(line)
        except Exception as e:
            assert self.exceptions
            self.exceptions(e)


class Microphone(STTStream):

    def __init__(self,
                 samplerate: int = 16_000,
                 blocksize: int = 100,
                 callback: AudioCallback | None = None,
                 ) -> None:
        super().__init__()
        self.stream = None
        self.blocksize = blocksize
        self.samplerate = samplerate
        self.callback: DifferedDef = callback

    def run(self):
        try:
            assert self.callback
            self.stream = Microphone.sd_stream(self.callback,
                                               self.uuid,
                                               self.samplerate,
                                               self.blocksize,
                                               AudioChannels.MONO)
            self.stream.start()
            print("Device: Microphone online")
        except Exception as e:
            assert self.exceptions
            self.exceptions(e)

    def start(self):
        self.run()
        assert self.stream

    def stop(self):
        assert self.stream
        self.stream.stop()

    @staticmethod
    def sd_stream(callback: AudioCallback,
                  device_id: uuid.UUID,
                  samplerate: int,
                  blocksize: int,
                  channels: int,
                  ):

        def wrapper(indata, frames, time, status):
            del frames, status

            def mono(indata):
                if indata.shape[1] == 1:
                    return indata[:, 0].copy()
                else:
                    return indata.mean(axis=1)

            callback(
                    AudioChunk(
                        device_id=device_id,
                        waveform=mono(indata),
                        samplerate=samplerate,
                        start_time=time.inputBufferAdcTime
                        )
                    )

        import sounddevice as sd
        return sd.InputStream(
                samplerate=samplerate,
                channels=channels,
                dtype="float32",
                blocksize=blocksize,
                callback=wrapper,
                )


class Keyboard(InputStream):
    ...
        

class Devices:
    Tcp = Tcp
    Fifo = Fifo
    Ollama = Ollama
    Microphone = Microphone
