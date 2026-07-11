from __future__ import annotations
from typing import TYPE_CHECKING

from regex import E

if TYPE_CHECKING:
    from .devices import InputStream

from uuid import UUID
from typing import Callable
from queue import Empty, Queue
from collections.abc import Generator
from pfspeak.core.types import ServiceTypes

from pfspeak.common.dataclasses import PfEvent
from pfspeak.core.runtime.marshal import Marshal
from pfspeak.common.g2p import Graphemes2Phonemes
from pfspeak.core.runtime.buffer import AudioRecognizer
from pfspeak.common.just_checking import TypeRecognizer


class PfSession:

    def __init__(self,
                 g2p: Graphemes2Phonemes,
                 worker: Callable,
                 recognizer: TypeRecognizer,
                 ) -> None:
        self.events_queue: Queue[PfEvent] = Queue()
        self.exceptions: Queue[BaseException] = Queue()
        self.tts = Marshal(worker, self.events_queue.put, self.exceptions.put)
        self.stt = AudioRecognizer(g2p,
                                   recognizer,
                                   self.events_queue.put,
                                   self.exceptions.put,)
        self.devices: dict[UUID, InputStream] = {}
        self.__keep_alive = True
        g2p.ensure("a")


    def add_device(self, device: InputStream) -> None:
        if device.device_id in self.devices:
            raise RuntimeError("Duplicate session device")
        self.devices[device.device_id] = device
        device.submit_exceptions = self.exceptions.put

        if device.service is ServiceTypes.STT:
            device.callback = self.stt.factory(self.stt.recognizer_adapter)
        else:
            device.callback = self.events_queue.put

    def shutdown(self):
        self.__keep_alive = False

    def reset(self, device: InputStream) -> None:
        self.stt.reset(device.device_id)
        device.active = None

    def finalize(self, event: PfEvent):
        if event.finalized:
            raise RuntimeError("Event already finalized")
        assert event.device
        event.finalized = True
        event.device.active = None
        self.reset(event.device)
        self.events_queue.put(event)

    def __poll_cycle(self):
        for device in self.devices.values():
            if device.active:
                yield device.active 
        try:
            yield self.events_queue.get(timeout=0.015)
        except Empty:
            yield PfEvent.as_ticket()

    def __iter__(self) -> Generator[PfEvent]:
        while self.__keep_alive:
            for event in self.__poll_cycle():

                if not self.exceptions.empty():
                    raise self.exceptions.get_nowait()

                if event.device_id:
                    event.device = self.devices[event.device_id]
                    if event.service is event.types.STT and not event.finalized:
                        event.device.active = event

                yield event

                match event.service:
                    case PfEvent.EventTypes.TEXT:
                        assert event.request
                        self.tts(event.request)

    def __enter__(self):
        self.tts.start()
        for device in self.devices.values():
             device.start()
        return self

    def __exit__(self, *args):
        print("Session: shutting down")
        self.tts.stop()
        for device in self.devices.values():
            device.stop()
        if args[1] is not None:
            return False
        if not self.exceptions.empty():
            raise self.exceptions.get_nowait()
        return False
