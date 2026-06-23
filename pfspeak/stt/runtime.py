import time


from pfspeak.common import models, Result
from pfspeak.common.dataclasses import TokenList
from pfspeak.common.defaults import AppSpec

from typing import Callable, List

from pfspeak.common.just_checking import TypeRecognizer

from pfspeak.stt.buffer import ListenBuffer
from pfspeak.stt.recognizers import KrokoRecognizerSpec
from pfspeak.stt.stream import Microphone
from pfspeak.common.defaults import (
        DEFAULT_APP_SPEC,
        )


def results_time(results: List[Result]) -> float:
    assert results[-1].tokens.tokens[-1].start_ts
    return results[-1].tokens.tokens[-1].start_ts


class SpeechToText:
    def __init__(self,
                 app_spec: AppSpec | None = None,
                 runtime_spec: KrokoRecognizerSpec | None = None
                 ) -> None:

        self.app_spec = app_spec or DEFAULT_APP_SPEC
        self.runtime_spec = runtime_spec or KrokoRecognizerSpec()

        self.download = models.install_model(self.app_spec, self.runtime_spec)

        self.results: List[Result] = []
        self.latest: Result = Result([], TokenList())

    @property
    def local_dir(self):
        return self.runtime_spec.resolv_local_dir(self.app_spec)

    @property
    def postfix(self) -> str:
        if self.runtime_spec.onnx:
            return ".onnx"
        return ""

    @property
    def tokens(self) -> str:
        return str(self.local_dir / "tokens.txt")

    def with_postfix(self, filename: str) -> str:
        return str(self.local_dir / (filename + self.postfix))

    @property
    def encoder(self) -> str:
        return  self.with_postfix("encoder")

    @property
    def decoder(self) -> str:
        return self.with_postfix("decoder")

    @property
    def joiner(self) -> str:
        return self.with_postfix("joiner")

    def secure_model(self):
        if self.local_dir.exists():
            return
        filename = self.download()
        assert filename == self.local_dir, filename

    def to_recognizer(self) -> TypeRecognizer:
        from sherpa_onnx import OnlineRecognizer

        if not self.local_dir.exists():
            raise RuntimeError("Could not find model in data root directory")

        if not self.runtime_spec.is_a_streaming_model:
            raise RuntimeError("Don't forget to get the streaming model.")

        kwargs = dict()
        if self.runtime_spec.hot_words:
            kwargs["decoding_method"] = "modified_beam_search"
            kwargs["hotwords_score"] = float(self.runtime_spec.hot_words_bias)
            kwargs["hot_words"] = " ".join(self.runtime_spec.hot_words)

        return OnlineRecognizer.from_transducer(
            tokens=self.tokens,
            encoder=self.encoder,
            decoder=self.decoder,
            joiner=self.joiner,
            num_threads=self.runtime_spec.treads,
            sample_rate=self.runtime_spec.samplerate,
            feature_dim=self.runtime_spec.feature_dim,
            **kwargs,
        )


    def prepare_stream(self):
        self.buffer = ListenBuffer(self.runtime_spec, self.to_recognizer)
        callback = self.buffer.callback_factory()
        self.stream = Microphone(self.runtime_spec, callback)

    def start(self):
        self.secure_model()
        self.prepare_stream()
        self.stream.start()

    def runforever(self):
        print("Pfspeak: starting...")
        self.start()
        print("Ready")
        while True:
            if (ret := self.buffer.get_final()):
                self.on_final(ret)
            if (ret := self.buffer.get_partial()):
                self.on_partial(ret)
                return
            time.sleep(self.runtime_spec.latency)

    def on_partial(self, result: Result):
        if self.latest:
            self.latest = Result(
                    [self.latest.waveform, result.waveform],
                    result.tokens
                    )
        else:
            self.latest = result

    def on_final(self, result: Result):
        self.results.append(result)
        self.latest = result

    def close(self):
        self.stream.close()

    def __enter__(self):
        self.start()
        return self
        
    def __exit__(self, *_):
        self.close()

