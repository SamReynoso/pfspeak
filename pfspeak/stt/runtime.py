from pathlib import Path
import time

import sounddevice as sd

from pfspeak.common.dataclasses import Result, TokenList
from pfspeak.common.defaults import MODEL_NAMES
from pfspeak.common.g2p import get_g2p_for_lang
from pfspeak.stt.recognizers import RecognizerSpec, Language, ModelType


class KrokoRecognizerScpec(RecognizerSpec):
    model_directory: str = MODEL_NAMES['sherpa-zipformer']
    model_type: str = ModelType.ZIPFORMER

    samplerate: int = 16_000
    feature_dim: int = 80

    language: str = Language.ENGLISH
    is_a_streaming_model: bool = True
    onnx: bool = True

start_time = time.time()

class ListenTo:
    def __init__(self, spec: RecognizerSpec) -> None:
        self.spec = spec
        self.recognizer = self.spec.to_recognizer()
        self.waveform_buffer = []
        self.text_buffer = []
        self.exit_condition = False
        self.g2p = get_g2p_for_lang("a")
        self.last_text = ""

    def has_received_kill_signal(self):
        if time.time() - start_time > 8:
            return True
        else:
            return self.exit_condition

    def get_results(self):
        for i, text in enumerate(self.text_buffer):
            waveform = self.waveform_buffer[i]
            _, tokens = self.g2p(text)
            assert isinstance(tokens, list)
            result = Result(waveform, TokenList(tokens))
            yield result
        self.waveform_buffer= []
        self.text_buffer= []

    def decode_stream(self, stream):
        while self.recognizer.is_ready(stream):
            self.recognizer.decode_stream(stream)
        return self.recognizer.get_result(stream)

    def callback_factory(self):
        stream = self.recognizer.create_stream()

        def callback(indata, *_):  # indata, frames, time, status
            if indata.shape[1] == 1:
                waveform = indata[:, 0]
            else:
                waveform = indata.mean(axis=1)

            stream.accept_waveform(self.spec.samplerate, waveform)

            text = self.decode_stream(stream)
            if text != self.last_text:
                self.last_text = text
                self.text_buffer.append(text)
                self.waveform_buffer.append(waveform)

        return callback


class Microphone:
    def __init__(self, spec, callback):
        self.spec = spec
        self.callback = callback
        self.stream = None

    def start(self):
        self.stream = sd.InputStream(
                samplerate=self.spec.samplerate,
                channels=Channels.MONO,
                dtype="float32",
                blocksize=self.spec.blocksize,
                callback=self.callback,
                )
        self.stream.start()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()


class Runtime:
    def __init__(self) -> None:
        path = Path("/home/gabby/.local/share/pfspeak")
        self.spec = KrokoRecognizerScpec(data_dir=path)
        self._kill_on = None

    def start(self):
        self.buffer = ListenTo(self.spec)
        callback = self.buffer.callback_factory()
        self.stream = Microphone(self.spec, callback)
        self.stream.start()

    def close(self):
        self.stream.close()

    def __enter__(self):
        self.start()
        return self
        
    def __exit__(self, *_):
        self.close()

    def run_until_killed(self, on_result):
        while True:
            on_result(self.buffer)
            if self.buffer.has_received_kill_signal():
                return


def on_result(buffer):
    for result in buffer.get_results():
        print(result.text)
        ...

if __name__ == "__main__":
    with Runtime() as runtime:
        runtime.run_until_killed(on_result)
