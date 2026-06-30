import os
import json
import socket
from pathlib import Path
from threading import Thread
from multiprocessing import Queue
from abc import ABC, abstractmethod
from pfspeak.core.params import AudioChannels
from pfspeak.common.types import AudioCallback, PathLike
from pfspeak.common.requests import OllamaRequest
from pfspeak.common.dataclasses import AudioChunk
from pfspeak.core.session import STTSession, TTSSession
from pfspeak.common.types import DifferedDef, VoidableDef



class InputStream(ABC):

    SESSIONIZER = None

    def __init__(self, callback: DifferedDef = None) -> None:
        super().__init__()
        self.callback: DifferedDef = callback
        self.streaming = False
        self.recordings = []

    @abstractmethod
    def run(self): ...

    def start(self):
        print("staring worker thread")
        self.streaming = True
        self.thread = Thread(target=self.run, daemon=True)
        self.thread.start()

    def stop(self):
        self.streaming = False
        if self.thread:
            self.thread.join()


class TTSStream(InputStream):
    SESSIONIZER = TTSSession
    

class STTStream(InputStream):
    SESSIONIZER = STTSession


class Ollama(TTSStream):
    def __init__(self, callback: AudioCallback | None = None) -> None:
        super().__init__()
        self.callback = callback
        self.resps = Queue()


    def adaptor(self, model: str, prompt: str):
        response = OllamaRequest(model=model, stream=False).request(prompt)
        buffer = ""
        for line in response.iter_lines():
            event = json.loads(line)

            if text := event.get("response"):
                buffer += text
            if len(buffer) > 50:
                self.resps.put(buffer)
                buffer = ""
        if buffer:
            self.resps.put(buffer)
            buffer = ""

    def run(self):
        assert self.callback
        while self.streaming:
            line = self.resps.get()
            print(line)
            self.callback(line)


class Fifo(TTSStream):
    def __init__(self, path: PathLike, callback: VoidableDef = None) -> None:
        super().__init__()
        self.path = Path(path)
        self.callback: VoidableDef = callback 
        self.streaming = False

    def run(self):
        print("running fifo")
        assert self.callback

        if not self.path.exists():
            os.mkfifo(self.path)

        fd = os.open(self.path, os.O_RDONLY | os.O_NONBLOCK)

        self.streaming = True
        with open(fd, "r") as fifo:
            while self.streaming:
                for line in fifo:
                    self.callback(line)


class Tcp(TTSStream):

    def __init__(self, host="127.0.0.1", port=8877, callback=None) -> None:
        super().__init__()
        self.host = host
        self.port = port
        self.callback=callback

    def run(self):

        assert self.callback

        with socket.socket() as server:
            conn, _ = server.accept()

            with conn:
                file = conn.makefile()

                for line in file:
                    self.callback(line.rstrip("\n"))


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
        print("running mic")
        assert self.callback
        self.stream = sd_stream(self.callback,
                                self.samplerate,
                                self.blocksize,
                                AudioChannels.MONO,
                                )
        self.stream.start()

    def start(self):
        self.run()
        assert self.stream

    def stop(self):
        assert self.stream
        self.stream.stop()
        
       

def sd_stream(callback: AudioCallback,
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

