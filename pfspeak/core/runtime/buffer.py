from threading import Lock
from pfspeak.common.dataclasses import (
        Audio,
        AudioChunk,
        PfEvent,
        PfStatus,
        Recording
        )
from pfspeak.common.types import DifferedDef
from pfspeak.common.g2p import Graphemes2Phonemes
from pfspeak.common.just_checking import TypeRecognizer


class ListenBuffer:

    LOOKBACH_BLOCKS = 200

    def __init__(self,
                 recognizer: TypeRecognizer,
                 g2p: Graphemes2Phonemes,
                 ) -> None:
        self.g2p = g2p
        self.__ducked = False
        self.status = PfStatus()
        self.stream_lock = Lock()
        self.recognizer = recognizer
        self._lookback: Audio = Audio()
        self.add_event: DifferedDef = None
        self.recording: Recording = Recording()

    def __create_stream(self):
        self.stream = self.recognizer.create_stream()

    def duck(self):
        print("ducking microphone for listening buffer")
        self.__ducked = True
        self.reset_stream()

    def unduck(self):
        self.__ducked = False
        self.reset_stream()

    def reset_stream(self):
        with self.stream_lock:
            self.recording = Recording()
            self.__create_stream()

    def send_event(self, service: PfEvent.EventTypes):
        assert self.recording
        assert self.add_event
        self.add_event(
                PfEvent(
                    device=None,
                    service=service,
                    status=self.status,
                    recording=self.recording,
                    device_id=self.recording.audio[0].device_id,
                    )
                )

    def recording_updated(self) -> None:
        if self.__ducked:
            return
        else:
            service = PfEvent.EventTypes.STT

        with self.stream_lock:
            self.send_event(service)

    def factory(self, samplerate: int):
        self.__create_stream()

        def lookback() -> Audio:
            if self.LOOKBACH_BLOCKS < len(self._lookback):
                audio = Audio(self._lookback[-self.LOOKBACH_BLOCKS:])
            else:
                audio = self._lookback
            self._lookback = Audio()
            return audio

        def decode_stream_to_text(chunk):
            self.stream.accept_waveform(samplerate, chunk.waveform)
            while self.recognizer.is_ready(self.stream):
                self.recognizer.decode_stream(self.stream)
            return self.recognizer.get_result(self.stream)

        def sideeffects(chunk):
            self._lookback.append(chunk)
            self.status.received += 1

        def compare_text(text: str):
            if text and  self.recording.text != text:
                tokens = self.g2p(text)
                with self.stream_lock:
                    self.recording.revise(tokens, lookback())
                self.recording_updated()

        def callback(chunk: AudioChunk):
            if not self.__ducked:
                text = decode_stream_to_text(chunk).strip()
                sideeffects(chunk)
                compare_text(text)

        return callback

    def stop(self):
        self.stream.close()
