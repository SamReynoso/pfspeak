from threading import Lock
from pfspeak.common.types import DifferedDef
from pfspeak.common.g2p import Graphemes2Phonemes
from pfspeak.common.just_checking import TypeRecognizer
from pfspeak.common.dataclasses import Audio, AudioChunk, PfEvent, PfStatus, Recording


class ListenBuffer:

    LOOKBACH_BLOCKS = 100

    def __init__(self,
                 recognizer: TypeRecognizer,
                 g2p: Graphemes2Phonemes,
                 ) -> None:

        self.status = PfStatus()

        self.recognizer = recognizer
        self.g2p = g2p

        self.recording: Recording = Recording()
        self.stream_lock = Lock()
        self._lookback: Audio = Audio()
        self.add_event: DifferedDef = None
        self.__ducked = False

    def __create_stream(self):
        self.stream = self.recognizer.create_stream()

    def duck(self):
        self.__ducked = True

    def unduck(self):
        self.__ducked = False

    def reset_stream(self):
        with self.stream_lock:
            self.recording = Recording()
            self.__create_stream()


    def recording_updated(self) -> None:
        with self.stream_lock:
            assert self.recording
            assert self.add_event
            self.add_event(
                    PfEvent(
                        device_id=self.recording.audio[0].device_id,
                        service=PfEvent.Types.STT,
                        recording=self.recording,
                        status=self.status,
                        )
                    )

    def factory(self, samplerate: int):
        self.__create_stream()

        def n_lookback_blocks() -> Audio:
            if self.LOOKBACH_BLOCKS < len(self._lookback):
                return Audio(self._lookback[-self.LOOKBACH_BLOCKS:])
            else:
                return self._lookback

        def decode_stream_to_text(waveform):
            self.stream.accept_waveform(samplerate, waveform)
            while self.recognizer.is_ready(self.stream):
                self.recognizer.decode_stream(self.stream)
            return self.recognizer.get_result(self.stream)

        def callback(audio: AudioChunk):
            if self.__ducked:
                return
            text = decode_stream_to_text(audio.waveform).strip()
            self._lookback.append(audio)
            self.status.received += 1

            if text and  self.recording.text != text:
                tokens = self.g2p(text)
                with self.stream_lock:
                    self.recording.revise(tokens, n_lookback_blocks())
                    self._lookback = Audio()
                self.status.sent = len(self.recording.audio)
                self.recording_updated()

        return callback

    def stop(self):
        self.stream.close()
