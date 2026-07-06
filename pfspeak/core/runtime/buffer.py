from uuid import UUID
from collections import deque
from pfspeak.common.dataclasses import AudioChunk
from pfspeak.common.just_checking import TypeRecognizer


class Recognition:
    def __init__(self, device_id: UUID, stream) -> None:
        self.currnt = ""
        self.stream = stream
        self.device_id = device_id
        self.lookback: deque = deque()

    def if_it_is_updated(self, text):
        if text != self.currnt:
            self.currnt = text
            return self

    def feed(self, chunk: AudioChunk, recognizer: RecognizerAdapter):
        self.lookback.append(chunk)
        text = recognizer.from_chunk(chunk, self.stream)
        return self.if_it_is_updated(text)


class PredictionBank:

    def __init__(self) -> None:
        self.__predictions: dict[UUID, Recognition] = {}

    def get(self, device_id: UUID, recognizer: RecognizerAdapter):
        if device_id not in self.__predictions:
            self.reset(device_id, recognizer)
        return self.__predictions[device_id]

    def reset(self, device_id: UUID, recognizer: RecognizerAdapter):
        predicion = Recognition(device_id, recognizer.create_stream())
        self.__predictions[device_id] = predicion

    def feed(self, chunk: AudioChunk, recognizer: RecognizerAdapter):
        return self.get(chunk.device_id, recognizer).feed(chunk, recognizer)


class AudioRecognizer:

    def __init__(self, add_prediction) -> None:
        self.add_prediction = add_prediction
        self.predictions: PredictionBank = PredictionBank()

    def factory(self, recognizer: RecognizerAdapter):
        def callback(chunk: AudioChunk):
            predicton = self.predictions.feed(chunk, recognizer)
            if predicton:
                self.add_prediction(predicton)
        return callback


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
