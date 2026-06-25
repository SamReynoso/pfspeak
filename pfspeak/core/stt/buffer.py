from threading import Lock
from pfspeak.common.dataclasses import Audio, Recording
from pfspeak.common.g2p import Graphemes2Phonemes
from pfspeak.core.stt.stream import AudioChunk
from pfspeak.common.just_checking import TypeRecognizer



class ListenBuffer:

    LOOKBACH_BLOCKS = 100

    def __init__(self,
                 recognizer: TypeRecognizer,
                 g2p: Graphemes2Phonemes,
                 ) -> None:
        self.recognizer = recognizer
        self.g2p = g2p

        self.recording = Recording()
        self.stream_lock = Lock()
        self._lookback: Audio = []

    def get(self) -> Recording:
        return self.recording

    def partial(self) -> Recording:
        return self.get()

    def finalize(self) -> Recording:
        with self.stream_lock:
            recording = self.get()
            self.rest_stream()
            return recording

    def rest_stream(self):
        self.recording = Recording()
        self.create_stream()

    def create_stream(self):
        self.stream = self.recognizer.create_stream()

    def callback_factory(self, samplerate: int):
        self.create_stream()

        def n_lookback_blocks() -> Audio:
            if self.LOOKBACH_BLOCKS < len(self._lookback):
                return self._lookback[-self.LOOKBACH_BLOCKS:]
            else:
                return self._lookback

        def decode_stream_to_text(waveform):
            self.stream.accept_waveform(samplerate, waveform)
            while self.recognizer.is_ready(self.stream):
                self.recognizer.decode_stream(self.stream)
            return self.recognizer.get_result(self.stream)

        def callback(audio: AudioChunk):
            text = decode_stream_to_text(audio.waveform).strip()
            self._lookback.append(audio)

            if text and  self.recording.text != text:
                tokens = self.g2p(text)
                self.recording.revise(tokens, n_lookback_blocks())
                self._lookback = []

        return callback
