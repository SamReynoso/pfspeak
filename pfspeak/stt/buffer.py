

from threading import Lock
import time
from typing import List

from pfspeak.tts.specs import G2PSpec
from pfspeak.stt.recognizers import KrokoRecognizerSpec
from pfspeak.common import Result
from pfspeak.common.g2p import Graphemes2Phonemes
from pfspeak.common.just_checking import NDArray


class ListenBuffer:
    def __init__(self, spec: KrokoRecognizerSpec, to_recognizer) -> None:

        self.spec = spec

        self.final_ready: bool = False
        self.waveform_buffer: List[NDArray] = []
        self.last_text = ""
        self.timestamp = None

        self.recognizer = to_recognizer()
        self.stream = self.recognizer.create_stream()
        
        self.g2p = Graphemes2Phonemes()
        self.g2p.load(spec=G2PSpec(), default_lang="a")
        self.stream_lock = Lock()

    def get_result(self):
        result = Result(
                tokens=self.g2p(self.last_text),
                waveform=self.waveform_buffer
                )
        result.apply_timestamp()
        return result

    def rest_stream(self):
        self.last_text = ""
        self.waveform_buffer = []
        self.stream = self.recognizer.create_stream()
        self.final_ready = False

    def finalize(self):
        if self.last_text:
            assert self.timestamp is not None
            if len(self.last_text) > 100 or time.time() - self.timestamp> 5:
                self.final_ready = True

    def get_partial(self):
        return self.get_result()

    def get_final(self):
        with self.stream_lock:
            if self.final_ready:
                result = self.get_result()
                self.rest_stream()
                return result

    def callback_factory(self):
        def decode_stream_to_text(waveform):
            self.stream.accept_waveform(self.spec.samplerate, waveform)
            while self.recognizer.is_ready(self.stream):
                self.recognizer.decode_stream(self.stream)
            return self.recognizer.get_result(self.stream)
        def mono(indata):
            if indata.shape[1] == 1:
                return indata[:, 0]
            else:
                return indata.mean(axis=1)

        def callback(*args):  # indata, frames, time, status
            waveform = mono(args[0])
            text = decode_stream_to_text(waveform)
            if text != self.last_text:
                with self.stream_lock:
                    if self.last_text == "":
                        self.timestamp = args[2].currentTime
                    self.last_text = text
                    self.waveform_buffer.append(waveform)
            self.finalize()
        return callback
