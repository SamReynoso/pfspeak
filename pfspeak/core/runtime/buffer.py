from threading import Lock
from collections import deque
from pfspeak.common.dataclasses import (
        Audio,
        PfEvent,
        PfStatus,
        Recording,
        AudioChunk,
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
        self._lookback: deque = deque()
        self.add_event: DifferedDef = None
        self.recording: Recording = Recording()

    def __create_stream(self):
        self.stream = self.recognizer.create_stream()

    def duck(self):
        print("Buffer: ducking microphone")
        self.reset_stream()
        with self.stream_lock:
            self.__ducked = True

    def unduck(self):
        print("Buffer: unducking microphone")
        self.reset_stream()
        with self.stream_lock:
            self.__ducked = False

    def reset_stream(self):
        print("Buffer: resetting stream")
        with self.stream_lock:
            self.__create_stream()
            self.recording = Recording()

    def __send_event(self, service: PfEvent.EventTypes):
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

    def __recording_updated(self) -> None:
        if self.__ducked:
            service = PfEvent.EventTypes.DUCK
        else:
            service = PfEvent.EventTypes.STT
        with self.stream_lock:
            self.__send_event(service)

    def factory(self, samplerate: int):
        self.__create_stream()

        def lookback() -> Audio:
            audio = Audio(self._lookback)
            self._lookback.clear()
            return audio

        def decode_stream_to_text(chunk):
            self.stream.accept_waveform(samplerate, chunk.waveform)
            while self.recognizer.is_ready(self.stream):
                self.recognizer.decode_stream(self.stream)
            return self.recognizer.get_result(self.stream)

        def sideeffects(chunk):
            if len(self._lookback) == self.LOOKBACH_BLOCKS:
                self._lookback.popleft()
            self._lookback.append(chunk)
            assert len(self._lookback) <= self.LOOKBACH_BLOCKS
            self.status.received += 1

        def compare_text(text: str):
            if text and  self.recording.text != text:
                tokens = self.g2p(text)
                with self.stream_lock:
                    self.recording.revise(tokens, lookback())
                self.__recording_updated()

        def callback(chunk: AudioChunk):
            text = decode_stream_to_text(chunk).strip()
            sideeffects(chunk)
            compare_text(text)

        return callback

    def stop(self):
        self.stream.close()
