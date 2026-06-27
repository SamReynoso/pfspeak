from abc import ABC, abstractmethod
from collections.abc import Generator
import os
from pathlib import Path
from pfspeak.common.defaults import AppSpec, RepoSpec, Voices
from pfspeak.common.g2p import Graphemes2Phonemes
from pfspeak.core.stt.stream import AudioSource
from pfspeak.core.stt.buffer import ListenBuffer
from pfspeak.common.dataclasses import Recording, Result
from pfspeak.core.tts.inference import SpeechModel
from pfspeak.core.tts.pipeline import PfPipeline


class STTSession:

    def __init__(self, device: AudioSource, buffer: ListenBuffer) -> None:
        self.recordings: list[Recording] = []
        self.device = device
        self.buffer = buffer
        self.is_muted = True

    def partials(self) -> Generator[Recording]:
        while True:
            yield self.peek()

    def peek(self) -> Recording:
        return self.buffer.partial()

    def finalize(self, recording: Recording) -> None:
        self.recordings.append(recording)
        self.buffer.rest_stream()

    def mute(self):
        if self.is_muted is True:
            return
        self.device.close()
        self.is_muted = True

    def unmute(self):
        if self.is_muted is False:
            return
        self.device.start()
        self.is_muted = False

    def __enter__(self, *_):
        self.device.start()
        self.is_muted = False
        return self

    def __exit__(self, *_):
        self.device.close()
        self.is_muted = True

class AudioSink:
    ...

class SpeakBuffer:
    ...

TextGenerator = Generator[str]

class InputStream(ABC):
    @abstractmethod
    def open(self) -> None: ...

    def read(self) -> TextGenerator: ...

    def close(self) -> None: ...


class Fifo(InputStream):
    def __init__(self, path: Path) -> None:
        self.path = path

    def open(self):
        self.fd = os.open(self.path, os.O_RDONLY | os.O_NONBLOCK)
        self.fifo = open(self.fd, "r")

    def read(self) -> TextGenerator:
        for line in self.fifo:
            yield line

    def close(self):
        self.fifo.close()


class TTSSession:

    def __init__(self,
                 app: AppSpec,
                 repo: RepoSpec,
                 g2p: Graphemes2Phonemes,
                 inpurt: InputStream,
                 ) -> None:
        self.pipeline = PfPipeline(app, repo, g2p)
        self.is_muted = False

    def read(self, text: str, voice: str | Voices) -> Generator[Result]:
        yield from self.pipeline(text, voice)

    def play(self, _: Result):

        ...

    def __enter__(self, *_):
        self.pipeline.start_worker()
        self.is_muted = False
        return self

    def __exit__(self, *_):
        self.pipeline.stop()
        self.is_muted = True
