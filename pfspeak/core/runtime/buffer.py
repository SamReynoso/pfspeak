from uuid import UUID
from collections import deque
from pfspeak.common.dataclasses import AudioChunk
from pfspeak.common.just_checking import TypeRecognizer


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


class PredictionBank:

    def __init__(self) -> None:
        self.__predictions: dict[UUID, Recognition] = {}

    def get(self, device_id: UUID, recognizer: RecognizerAdapter):
        if device_id not in self.__predictions:
            self.reset(device_id, recognizer)
        return self.__predictions[device_id]

    def reset(self, device_id: UUID, recognizer: RecognizerAdapter):
        prediction = Recognition(device_id, recognizer.create_stream())
        self.__predictions[device_id] = prediction

    def feed(self, chunk: AudioChunk, recognizer: RecognizerAdapter):
        device_id = chunk.device_id
        return self.get(device_id, recognizer).feed(chunk, recognizer)


class AudioRecognizer:

    def __init__(self, add_prediction) -> None:
        self.add_prediction = add_prediction
        self.__suspended_predictions = None
        self.predictions: PredictionBank = PredictionBank()

    def conflict(self):
        self.__suspended_predictions = self.predictions
        self.predictions = PredictionBank()

    def restore(self):
        if self.__suspended_predictions is None:
            raise RuntimeError
        self.predictions = self.__suspended_predictions
        self.__suspended_predictions = None

    def factory(self, recognizer: RecognizerAdapter):
        def callback(chunk: AudioChunk):
            prediction = self.predictions.feed(chunk, recognizer)
            if prediction:
                self.add_prediction(prediction)
        return callback
