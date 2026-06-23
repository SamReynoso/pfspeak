

from pfspeak.stt.recognizers import KrokoRecognizerSpec

from pfspeak.stt.recognizers  import AudioChannels

from typing import Callable

class Microphone:
    def __init__(self, runtime_spec: KrokoRecognizerSpec, callback: Callable):
        self.spec = runtime_spec
        self.callback = callback
        self.stream = None

    def verify(self):
        import sounddevice as sd
        self.stream = sd.InputStream(
                samplerate=self.spec.samplerate,
                channels=AudioChannels.MONO,
                dtype="float32",
                blocksize=self.spec.blocksize,
                callback=self.callback,
                )

    def start(self):
        self.verify()
        assert self.stream
        self.stream.start()

    def close(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.close()
