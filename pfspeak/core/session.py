from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .sources import InputStream

from queue import Queue
from typing import Callable
from collections.abc import Generator
from pfspeak.core.params import ListenParams
from pfspeak.common.types import OptionalSpec
from pfspeak.common.dataclasses import PfEvent
from pfspeak.core.stt.buffer import ListenBuffer
from pfspeak.core.tts.pipeline import PfPipeline
from pfspeak.common.g2p import Graphemes2Phonemes
from pfspeak.common.models import RecognizerAsset
from pfspeak.common.defaults import DEFAULT_APP_SPEC
from pfspeak.core.repos import RecognizerRepo, SpeechRepo


class STTSession:

    def __init__(self,
                 device: InputStream,
                 app: OptionalSpec = None,
                 repo: RecognizerRepo | None = None
                 ) -> None:
        app = app or DEFAULT_APP_SPEC
        repo = repo or RecognizerRepo()
        params = ListenParams()
        recognizer = RecognizerAsset.load(app, repo, params)
        g2p = Graphemes2Phonemes()

        self.device = device
        self.buffer = ListenBuffer(recognizer, g2p)
        self.device.callback = self.buffer.factory(16_000)

        self.events: list[PfEvent] = []
        self.is_muted = True
        self.stream = False

    def bind_event_queue(self, put: Callable):
        def emit(event: PfEvent):
            event._finalize_self = self.finalize
            put(event)
        self.buffer.add_event = emit

    def finalize(self, event: PfEvent) -> None:
        self.events.append(event)
        self.device.recordings.append(event.recording)
        self.buffer.rest_stream()

    def duck(self):
        self.buffer.duck()

    def unduck(self):
        self.buffer.unduck()

    def stop(self):
        self.stream = False

    def __enter__(self, *_):
        self.device.start()
        self.is_muted = False
        return self

    def __exit__(self, *_):
        self.device.stop()
        self.is_muted = True


class TTSSession:

    def __init__(self,
                 device: InputStream,
                 app: OptionalSpec = None,
                 repo: SpeechRepo| None = None
                 ) -> None:
        app = app or DEFAULT_APP_SPEC
        repo = repo or SpeechRepo()
        g2p = Graphemes2Phonemes()

        self.device = device
        self.pipeline = PfPipeline(app, repo, g2p)
        device.callback = self.pipeline.factory()

        self.stream = False

    def bind_event_queue(self, put: Callable):
        def emit(event: PfEvent):
            if event.recording:
                self.device.recordings.append(event.recording)
            put(event)

        self.pipeline.add_event = emit 

    def stop(self):
        self.stream = False

    def __enter__(self, *_):
        self.pipeline.start()
        self.device.start()
        return self

    def __exit__(self, *_):
        self.pipeline.stop()
        self.device.stop()


class PfSession:

    def __init__(self, devices: list[InputStream]) -> None:
        self.__services = []
        self.__events = Queue()
        self.__steams_active = False
        for device in devices:
            assert device.SESSIONIZER
            session = device.SESSIONIZER(device)
            session.bind_event_queue(self.__events.put)
            self.__services.append(session)

    def __iter__(self) -> Generator[PfEvent]:
        while self.__steams_active:
            yield self.__events.get()

    def stop(self):
        self.__steams_active = False

    def mute(self):
        for service in self.__services:
            if hasattr(service, 'buffer'):
                service.stop()

    def unmute(self):
        for service in self.__services:
            if hasattr(service, 'buffer'):
                service.start()

    def __enter__(self, *_):
        for service in self.__services:
            service.__enter__()
        self.__steams_active = True
        return self

    def __exit__(self, *_):
        for service in self.__services:
            service.__exit__()
        self.__steams_active = False
        return self
