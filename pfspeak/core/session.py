from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .devices import InputStream

from uuid import UUID, uuid4
from typing import Callable
from queue import Empty, Queue
from abc import ABC, abstractmethod
from collections.abc import Generator
from pfspeak.core.param import ListenParams
from pfspeak.common.types import OptionalSpec
from pfspeak.core.asset import RecognizerAsset
from pfspeak.common.g2p import Graphemes2Phonemes
from pfspeak.common.defaults import DEFAULT_APP_SPEC
from pfspeak.core.runtime.buffer import ListenBuffer
from pfspeak.core.runtime.pipeline import PfPipeline
from pfspeak.core.types import InProcess, WorkerProcess
from pfspeak.core.repo import RecognizerRepo, SpeechRepo
from pfspeak.common.dataclasses import PfEvent, PfStatus, Recording


class BaseSession(ABC):
    def __init__(self, app, repo) -> None:
        self.app = app
        self.repo = repo
        self.is_muted = True
        self.callback = None
        self.devices: dict[UUID, InputStream] = {}

    def add_device(self, device: InputStream) -> None:
        if self.__put_exception is None:
            raise RuntimeError(
                    "Attempting to device before binding exectpion queue")
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

    def create_pipeline(self) -> None:
        params = ListenParams()
        recognizer = RecognizerAsset(self.app, self.repo).load(params)
        g2p = Graphemes2Phonemes()
        self.buffer = ListenBuffer(recognizer, g2p)

    def bind_status(self, factory: Callable):
        self.buffer.bind_status(factory)

    def bind_event_queue(self, put: Callable) -> None:

        def emit(event: PfEvent) -> None:
            put(event)

        self.buffer.add_event = emit

    def duck(self) -> None:
        self.buffer.duck()

    def unduck(self) -> None:
        self.buffer.unduck()

    def __enter__(self, *_) -> STTSession:
        for device in self.devices.values():
            device.start()
        self.is_muted = False
        return self

    def __exit__(self, *_) -> None:
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

    def duck(self) -> None: ...
    def unduck(self) -> None: ...

    def bind_status(self, factory: Callable):
        self.pipeline.bind_status(factory)

    def bind_event_queue(self, put: Callable) -> None:

        def emit(event: PfEvent):
            if event.recording:
                self.devices[event.device_id].recordings.append(event.recording)
            put(event)

        self.pipeline.add_event = emit 

    def __enter__(self, *_) -> TTSSession:
        self.pipeline.start()
        for device in self.devices.values():
            device.start()
        self.is_muted = False
        return self

    def __exit__(self, *_) -> None:
        for device in self.devices.values():
            device.stop()
        self.pipeline.stop()
        self.is_muted = True


class PfSession:

    def __init__(self, *devices: InputStream) -> None:
        self.uuid = uuid4()
        self.__sessions_map = {}
        self.__sessions = [] 
        self.__workers= []
        self.__events = Queue()
        self.__exceptions = Queue()
        self.__devices: dict[UUID, InputStream] = {}
        self.status = PfStatus()
        self.statuses: dict[str, PfStatus] = {"Session": self.status}
        for device in devices:
            self.add_device(device)

    def register_status(self, name: str):
        status = PfStatus()
        self.statuses[name] = status
        return status

    def add_device(self, device: InputStream) -> None:
        if device.uuid in self.__devices:
            raise RuntimeError("Devices can only be added to a session once")

        self.__devices[device.uuid] = device
        device.bind_status(self.register_status)

        if device.SESSIONIZER.STRATEGY == WorkerProcess:
            if self.__workers:
                session = self.__workers[0]
            else:
                session = device.SESSIONIZER()
                self.__workers.append(session)
                self.__sessions.append(session)
                session.bind_status(self.register_status)
                session.bind_event_queue(self.__events.put)
                session.bind_exceptions(self.__exceptions.put)

        elif device.SESSIONIZER.STRATEGY == InProcess:
            session = device.SESSIONIZER()
            self.__sessions.append(session)
            session.bind_status(self.register_status)
            session.bind_event_queue(self.__events.put)
            session.bind_exceptions(self.__exceptions.put)

        else:
            raise ValueError("Unknow session worker strategy")

        session.add_device(device)
        self.__sessions_map[device.uuid] = session


    def __iter__(self) -> Generator[PfEvent]:
        while self.__streams_active:

            try:
                exc = self.__exceptions.get_nowait()

            except Empty:
                pass

            else:
                raise exc

            try:
                event: PfEvent = self.__events.get(timeout=.02)
                device = self.__devices[event.device_id]
                event.device = device
                if event.service != PfEvent.EventTypes.DUCK:
                    device._current = event
                yield event

            except Empty:
                yield PfEvent(
                        device_id=self.uuid,
                        device=None,
                        status=PfStatus(),
                        service=PfEvent.EventTypes.TICKET,
                        recording=Recording(),
                        )

    def mute(self) -> None:
        for session in self.__sessions:
            session.duck()

    def unmute(self) -> None:
        for session in self.__sessions:
            session.unduck()
        self.status.line = "waiting"

    def reset(self, device: InputStream) -> None:
        session = self.__sessions_map[device.uuid]
        if session.STRATEGY != InProcess:
            raise RuntimeError("Only in-process devices can be reset")

        session.buffer.reset_stream()
        device._current = None

    def finalize(self, event: PfEvent):
        assert event.device
        event.device.recordings.append(event.recording)
        self.status.line = "event finalized"
        self.reset(event.device)

    def __enter__(self, *_) -> PfSession:
        print("PfSession: starting")
        for sessions in self.__sessions:
            sessions.__enter__()

        self.__streams_active = True
        print("PfSession: READY")
        return self

    def __exit__(self, *_) -> None:
        print("PfSession: shutting down")
        for session in self.__sessions:
            session.__exit__(*_)
        self.__streams_active = False
