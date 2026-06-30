import os
import json
import socket
import uuid
from pathlib import Path
from threading import Thread
from multiprocessing import Queue
from abc import ABC, abstractmethod
from pfspeak.common.defaults import Voices
from pfspeak.core.param import AudioChannels
from pfspeak.common.requests import OllamaRequest
from pfspeak.core.session import STTSession, TTSSession
from pfspeak.common.types import AudioCallback, PathLike
from pfspeak.common.types import DifferedDef, VoidableDef
from pfspeak.common.dataclasses import AudioChunk, WorkRequest


class InputStream(ABC):

    SESSIONIZER: type[TTSSession] | type[STTSession]

    def __init__(self,
                 callback: DifferedDef = None,
                 voice: Voices | str | None = None,
                 speed: float = 1,

                 ) -> None:
        super().__init__()
        self.uuid = uuid.uuid4()
        self.callback: DifferedDef = callback
        self.recordings = []
        self.voice = voice
        self.speed = speed
        self.streaming = False
        self.exceptions: DifferedDef = None

    @abstractmethod
    def run(self): ...

    def start(self):
        self.streaming = True
        self.thread = Thread(target=self.run, daemon=True)
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
                text=text,
                speed=self.speed,
                voice=self.voice,
                )
        assert self.callback
        self.callback(req)
    

class STTStream(InputStream):

    SESSIONIZER = STTSession


class Ollama(TTSStream):
    def __init__(self, callback: AudioCallback | None = None) -> None:
        super().__init__()
        self.callback = callback
        self.requests = Queue()


    def adaptor(self, model: str, prompt: str):
        self.requests.put((model, prompt))

    def run(self):
        try:
            print("Ollama device online")
            while self.streaming:
                model, prompt = self.requests.get()
                ollama = OllamaRequest(model=model, stream=False)
                response = ollama.request(prompt)
                event = response.json()
                if text := event.get("response"):
                    self.request(text)
        except Exception as e:
            assert self.exceptions
            self.exceptions(e)


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

            print("Fifo device online")
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

                print("Tcp device online")
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
        self.samplerate = samplerate
        self.blocksize = blocksize
        self.callback: DifferedDef = callback
        self.stream = None

    def run(self):
        try:
            assert self.callback
            self.stream = Microphone.sd_stream(self.callback,
                                               self.uuid,
                                               self.samplerate,
                                               self.blocksize,
                                               AudioChannels.MONO)
            self.stream.start()
            print("Microphone device online")
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
                        waveform = mono(indata),
                        samplerate=samplerate,
                        start_time = time.inputBufferAdcTime
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
