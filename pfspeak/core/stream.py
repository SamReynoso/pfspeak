from collections.abc import Generator
from pfspeak.core.stt.stream import AudioSource
from pfspeak.core.stt.buffer import ListenBuffer
from pfspeak.common.dataclasses import Recording


class Session:

    def __init__(self, device: AudioSource, buffer: ListenBuffer) -> None:
        self.recordings: list[Recording] = []
        self.is_muted = True
        self.device = device
        self.buffer = buffer
        self.muted = False

    def partials(self) -> Generator[Recording]:
        while True:
            yield self.peek()

    def peek(self) -> Recording:
        return self.buffer.partial()

    def finalize(self, recording: Recording) -> None:
        self.recordings.append(recording)
        self.buffer.rest_stream()

    def mute(self):
        if self.is_muted is True:
            return
        self.device.close()
        self.is_muted = True

    def unmute(self):
        if self.is_muted is False:
            return
        self.device.start()
        self.is_muted = False

    def __enter__(self, *_):
        self.device.start()
        self.is_muted = False
        return self

    def __exit__(self, *_):
        self.device.close()
        self.is_muted = True



Text = str

