from __future__ import annotations
from typing import TYPE_CHECKING
from uuid import UUID

from pfspeak.common.g2p import Graphemes2Phonemes

if TYPE_CHECKING:
    from .devices import InputStream

from queue import Empty, Queue
from collections.abc import Generator
from pfspeak.core.runtime.buffer import (
        AudioRecognizer,
        Recognition,
        RecognizerAdapter
        )
from pfspeak.common.just_checking import TypeRecognizer
from pfspeak.core.runtime.pipeline import PipelineConnections, WorkerAdapter
from pfspeak.common.dataclasses import Audio, PfEvent, Prediction, Recording


class PfBackend:
    @classmethod
    def is_compatiable(cls, device: InputStream):
        return issubclass(device.BACKEND, cls)


class SttBackend(PfBackend):

    def __init__(self, g2p, event_queue, recognizer: TypeRecognizer) -> None:
        self.g2p = g2p
        self.event_queue = event_queue
        self.recognizer = AudioRecognizer(self.add_prediction)
        self.recognizer_adapter = RecognizerAdapter(recognizer)

    def add_prediction(self, prediction: Recognition):
        event = PfEvent(service=PfEvent.EventTypes.STT,
                        device=None,
                        device_id=prediction.device_id,
                        finalized=False,
                        recording=Recording(tokens=self.g2p(prediction.currnt),
                                            audio=Audio(prediction.lookback)
                                            )
                        )
        self.event_queue.put(event)

    def add_device(self, device: InputStream) -> None:
        device.callback = self.recognizer.factory(self.recognizer_adapter)

class TtsBackend(PfBackend):

    def __init__(self, g2p, events_queue, exceptions, worker) -> None:
        self.g2p = g2p 
        self.exceptions = exceptions
        self.events_queue = events_queue
        self.pipeline = PipelineConnections(worker,
                                            self.add_prediction,
                                            exceptions)

    def add_prediction(self, prediction: Prediction):
        event = prediction.as_event()
        self.events_queue.put(event)

    def add_device(self, device: InputStream):
        device.callback = self.pipeline.factory()


class PfSession:

    def __init__(self,
                 g2p: Graphemes2Phonemes,
                 worker: WorkerAdapter,
                 recognizer: TypeRecognizer,
                 ) -> None:
        self.events_queue: Queue[PfEvent] = Queue()
        self.exceptions: Queue[BaseException] = Queue()
        self.devices: dict[UUID, InputStream] = {}
        self.tts: TtsBackend = TtsBackend(g2p,
                                          self.events_queue,
                                          self.exceptions, worker)
        self.stt: SttBackend = SttBackend(g2p, self.events_queue, recognizer)
        self.muted: bool = True

    def add_devices(self, devices):
        for device in devices:
            self.add_device(device)

    def add_device(self, device: InputStream) -> None:
        if device.device_id in self.devices:
            raise RuntimeError("Duplicate session device")
        self.devices[device.device_id] = device
        if SttBackend.is_compatiable(device):
            self.stt.add_device(device)
        elif TtsBackend.is_compatiable(device):
            self.tts.add_device(device)

    def mute(self) -> None:
        self.muted = True

    def unmute(self) -> None:
        self.muted = False

    def reset(self, device: InputStream) -> None:
        self.stt.recognizer.predictions.reset(device.device_id, self.stt.recognizer_adapter)

    def finalize(self, event: PfEvent):
        assert event.device
        event.finalized = True
        self.reset(event.device)

    def __iter__(self) -> Generator[PfEvent]:
        while True:
            if not self.exceptions.empty():
                raise self.exceptions.get_nowait()

            try:
                event: PfEvent = self.events_queue.get(timeout=.02)
                assert event.device_id
                event.device =  self.devices[event.device_id]
                if self.muted:
                    event.service = PfEvent.EventTypes.DUCK
                else:
                    event.device._current = event
                yield event
            except Empty:
                yield PfEvent(
                        device=None,
                        finalized=False,
                        device_id=None,
                        service=PfEvent.EventTypes.TICKET,
                        recording=Recording(),
                        )

    def __enter__(self):
        self.tts.pipeline.start()
        for device in self.devices.values():
            device.start()
        return self

    def __exit__(self, *_):
        print("Shutting down session")
        self.tts.pipeline.join()
        for device in self.devices.values():
            device.stop()
