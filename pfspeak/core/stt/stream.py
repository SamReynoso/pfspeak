
from abc import ABC, abstractmethod
from typing import Callable

from pfspeak.common.dataclasses import AudioCallback, AudioChunk

from pfspeak.core.params import AudioChannels, ListenParams


CallbackFactory = Callable[[int], AudioCallback] 


class AudioSource(ABC):
    def __init__(self,
                 params: ListenParams,
                 callback: AudioCallback | None = None,
                 callback_factory: CallbackFactory | None = None,
                 ) -> None:
        assert callback or callback_factory 
        assert not (callback and callback_factory)
        self.params = params
        self._callback = callback
        self._callback_factory = callback_factory
        self.stream = None


    @abstractmethod
    def audio_adaptor(self, *args, **kwargs): ...

    @abstractmethod
    def prepare(self): ...

    def start(self):
        self.prepare()
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


class Microphone(AudioSource):

    def audio_adaptor(self, indata, frames, time, status):
        del frames, status

        def mono(indata):
            if indata.shape[1] == 1:
                return indata[:, 0].copy()
            else:
                return indata.mean(axis=1)

        self._callback(
                AudioChunk(
                    waveform = mono(indata),
                    samplerate=self.params.samplerate,
                    start_time = time.inputBufferAdcTime
                    )
                )

    def prepare(self):
        import sounddevice as sd
        if self._callback_factory:
            self._callback = self._callback_factory(self.params.samplerate)
        self.stream = sd.InputStream(
                samplerate=self.params.samplerate,
                channels=AudioChannels.MONO,
                dtype="float32",
                blocksize=self.params.blocksize,
                callback=self.audio_adaptor,
                )
