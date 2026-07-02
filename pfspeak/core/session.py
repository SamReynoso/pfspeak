from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .devices import InputStream

from uuid import UUID
from typing import Callable
from queue import Empty, Queue
from abc import ABC, abstractmethod
from collections.abc import Generator
from pfspeak.core.param import ListenParams
from pfspeak.common.types import OptionalSpec
from pfspeak.core.asset import RecognizerAsset
from pfspeak.common.dataclasses import PfEvent
from pfspeak.common.g2p import Graphemes2Phonemes
from pfspeak.common.defaults import DEFAULT_APP_SPEC
from pfspeak.core.runtime.buffer import ListenBuffer
from pfspeak.core.runtime.pipeline import PfPipeline
from pfspeak.core.repo import RecognizerRepo, SpeechRepo
from pfspeak.core.types import InProcess, WorkerProcess


class BaseSession(ABC):
    def __init__(self, app, repo) -> None:
        self.app = app
        self.repo = repo
        self.devices: dict[UUID, InputStream] = {}
        self.is_muted = True
        self.callback = None

    def add_device(self, device: InputStream) -> None:
        assert self.__put_exception
        device.callback = self.callback
        device.exceptions = self.__put_exception
        self.devices[device.uuid] = device

    def bind_exceptions(self, put: Callable) -> None:
        self.__put_exception = put

    @abstractmethod
    def bind_event_queue(self, put: Callable) -> None: ...

    @abstractmethod
    def duck(self) -> None: ...

    @abstractmethod
    def unduck(self) -> None: ...

    @abstractmethod
    def __enter__(self, *_) -> BaseSession: ...

    @abstractmethod
    def __exit__(self, *_) -> None: ...


class STTSession(BaseSession):

    STRATEGY = InProcess

    def __init__(self,
                 app: OptionalSpec = None,
                 repo: RecognizerRepo | None = None,
                 ) -> None:
        super().__init__(app or DEFAULT_APP_SPEC, repo or RecognizerRepo())
        self.create_pipeline()
        self.callback = self.buffer.factory(16_000)

    def create_pipeline(self):
        params = ListenParams()
        recognizer = RecognizerAsset(self.app, self.repo).load(params)
        g2p = Graphemes2Phonemes()
        self.buffer = ListenBuffer(recognizer, g2p)

    def bind_event_queue(self, put: Callable):

        def finalize(event: PfEvent) -> None:
            self.devices[event.device_id].recordings.append(event.recording)
            self.buffer.reset_stream()
            put(event)

        def emit(event: PfEvent):
            event._finalize_self = finalize
            put(event)

        self.buffer.add_event = emit

    def duck(self):
        self.buffer.duck()

    def unduck(self):
        self.buffer.unduck()

    def __enter__(self, *_):
        for device in self.devices.values():
            device.start()
        self.is_muted = False
        return self

    def __exit__(self, *_):
        for device in self.devices.values():
            device.stop()
        self.is_muted = False


class TTSSession(BaseSession):

    STRATEGY = WorkerProcess

    def __init__(self,
                 app: OptionalSpec = None,
                 repo: SpeechRepo | None = None
                 ) -> None:
        super().__init__(app or DEFAULT_APP_SPEC, repo or SpeechRepo())
        g2p = Graphemes2Phonemes()
        self.pipeline = PfPipeline(self.app, self.repo, g2p)
        self.callback = self.pipeline.factory()

    def bind_event_queue(self, put: Callable):

        def emit(event: PfEvent):
            if event.recording:
                self.devices[event.device_id].recordings.append(event.recording)
            put(event)

        self.pipeline.add_event = emit 

    def __enter__(self, *_):
        self.pipeline.start()
        for device in self.devices.values():
            device.start()
        self.is_muted = False
        return self

    def __exit__(self, *_):
        for device in self.devices.values():
            device.stop()
        self.pipeline.stop()
        self.is_muted = True

    def duck(self) -> None: ...
    def unduck(self) -> None: ...

class PfSession:

    def __init__(self, *devices: InputStream) -> None:
        self.__in_process = []
        self.__services = {}
        self.sessions = []
        self.__exceptions = Queue()
        self.__events = Queue()

        for device in devices:

            if device.SESSIONIZER.STRATEGY == WorkerProcess:

                if not self.__in_process:
                    session = device.SESSIONIZER()
                    self.__in_process.append(session)
                    self.sessions.append(session)

                session = self.__in_process[0]

            elif device.SESSIONIZER.STRATEGY == InProcess:
                session = device.SESSIONIZER()
                self.sessions.append(session)

            else:
                raise ValueError("Unknow session worker strategy")

            session.bind_event_queue(self.__events.put)
            session.bind_exceptions(self.__exceptions.put)
            session.add_device(device)
            self.__services[device.uuid] = session

    def __iter__(self) -> Generator[PfEvent]:
        while self.__streams_active:
            try:
                exc = self.__exceptions.get_nowait()
            except Empty:
                pass
            else:
                raise exc

            try:
                yield self.__events.get(timeout=1)
            except Empty:
                pass

    def mute(self):
        for session in self.sessions:
            session.duck()

    def unmute(self):
        for session in self.sessions:
            session.unduck()

    def __enter__(self, *_):
        print("Starting PfSession")
        for sessions in self.sessions:
            sessions.__enter__()

        self.__streams_active = True
        print("PfSession started")
        return self

    def __exit__(self, *_):
        print("PfSession shutting down")
        for session in self.sessions:
            session.__exit__()
        self.__streams_active = False
        print("PfSession shutdown complete")
        print("bye")
