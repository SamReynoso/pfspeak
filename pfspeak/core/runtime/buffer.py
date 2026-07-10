from typing import Callable
from uuid import UUID
from collections import deque
#from pfspeak.common.g2p import Graphemes2Phonemes
from pfspeak.common.just_checking import TypeRecognizer
from pfspeak.common.dataclasses import Audio, AudioChunk, PfEvent, Recording


class RecognizerAdapter:

    def __init__(self, recognizer: TypeRecognizer) -> None:
        self.recognizer = recognizer

    def from_chunk(self, chunk: AudioChunk, stream):
        stream.accept_waveform(chunk.samplerate, chunk.waveform)
        while self.recognizer.is_ready(stream):
            self.recognizer.decode_stream(stream)
        return self.recognizer.get_result(stream).strip()

    def create_stream(self):
        return self.recognizer.create_stream()


class Recognition:

    MAX_LOOKBACK = 99

    def __init__(self, device_id: UUID, stream) -> None:
        self.text = ""
        self.stream = stream
        self.device_id = device_id
        self.lookback: deque = deque()

    def append(self, chunk: AudioChunk):
        self.lookback.append(chunk)
        if len(self.lookback) > self.MAX_LOOKBACK:
            self.lookback.popleft()

    def if_it_is_updated(self, text):
        if text != self.text:
            self.text = text
            return self

    def feed(self, chunk: AudioChunk, recognizer: RecognizerAdapter):
        text = recognizer.from_chunk(chunk, self.stream)
        self.append(chunk)
        return self.if_it_is_updated(text)

    def __repr__(self) -> str:
        return (f"Recognition(text-length:{len(self.text)}, "
                f"lookback-count:{len(self.lookback)})")


class PredictionBank:

    def __init__(self) -> None:
        self.__predictions: dict[UUID, Recognition] = {}

    def get(self, device_id: UUID, recognizer: RecognizerAdapter):
        if device_id not in self.__predictions:
            self.reset(device_id, recognizer)
        return self.__predictions[device_id]

    def reset(self, device_id: UUID, recognizer: RecognizerAdapter):
        stream = recognizer.create_stream()
        self.__predictions[device_id] = Recognition(device_id, stream)

    def feed(self, chunk: AudioChunk, recognizer: RecognizerAdapter):
        device_id = chunk.device_id
        return self.get(device_id, recognizer).feed(chunk, recognizer)


class AudioRecognizer:

    def __init__(self,
                 g2p:  Graphemes2Phonemes,
                 recognizer: TypeRecognizer,
                 submit_event: Callable,
                 add_prediction: Callable
                 ) -> None:
        self.g2p = g2p
        self.recognizer_adapter = RecognizerAdapter(recognizer)

        self.cycle: dict[UUID, Recording] = {}
        self.__suspended_predictions = None
        self.predictions: PredictionBank = PredictionBank()

        self.submit_event = submit_event
        self.add_prediction = add_prediction

        self.service = PfEvent.EventTypes.STT

    def get_or_create(self, prediction: Recognition) -> Recording:

        device_id = prediction.device_id
        tokens = self.g2p(prediction.text)
        audio = Audio(prediction.lookback) 

        if device_id in self.cycle:
            self.cycle[device_id].revise(tokens, audio)

        else:
            self.cycle[device_id] = Recording(tokens=tokens, audio=audio)

        self.cycle[device_id].apply_timestamp()
        return self.cycle[device_id]

    def __add_prediction(self, prediction: Recognition) -> None:
        recording = self.get_or_create(prediction)
        assert recording is not None
        event = PfEvent(device_id=prediction.device_id,
                        service=self.service,
                        recording=recording,
                        finalized=False,
                        request=None,
                        device=None)
        self.submit_event(event)

    def conflict(self):
        self.__suspended_predictions = self.predictions
        self.predictions = PredictionBank()

    def restore(self):
        if self.__suspended_predictions is None:
            raise RuntimeError
        self.predictions = self.__suspended_predictions
        self.__suspended_predictions = None

    def mute(self):
        self.conflict()
        self.service = PfEvent.EventTypes.DUCK
        self.cycle = {}

    def unmute(self):
        self.restore()
        self.service = PfEvent.EventTypes.STT
        self.cycle = {}

    def reset(self, device_id: UUID) -> None:
        del self.cycle[device_id]
        self.predictions.reset(device_id, self.recognizer_adapter)

    def factory(self, recognizer: RecognizerAdapter):
        def callback(chunk: AudioChunk):
            prediction = self.predictions.feed(chunk, recognizer)
            if prediction:
                self.__add_prediction(prediction)
        return callback
