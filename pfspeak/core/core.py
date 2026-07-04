import heapq
import itertools
import sounddevice
from uuid import UUID
from pfspeak.extra.voices import Voices
from pfspeak.app.directories import build
from pfspeak.core.types import ServiceTypes
from pfspeak.core.asset import follow_policy
from pfspeak.core.devices import InputStream
from pfspeak.common.types import OptionalSpec
from pfspeak.core.devices import Devices, Hook
from pfspeak.core.repo import RecognizerRepo, SpeechRepo
from pfspeak.common.dataclasses import PfEvent, Playback
from pfspeak.common.defaults import DEFAULT_APP_SPEC, AppSpec
from pfspeak.core.session import PfSession, STTSession, TTSSession

LastEvents = dict[tuple[PfEvent.EventTypes, UUID], PfEvent]
PlaybackBuffer = list[Playback]

class PfSpeak:
    """
    High-level entry point for creating speech applications.

    PfSpeak provides a small convenience layer around the lower-level session
    APIs.

    Responsibilities include:

    - preparing required speech assets
    - constructing a PfSession from one or more devices
    - managing optional text-to-speech playback
    - exposing common debugging helpers

    Typical usage:

        pf = PfSpeak()
        session = pf.streaming(Microphone(), Ollama())
        for event in session:
            pf.print(event)

    Applications that require finer control may interact with PfSession
    directly.
    """

    voices = Voices
    devices = Devices
    AppSpec = AppSpec

    def __init__(self, app: OptionalSpec = None) -> None:
        self.__app = app or DEFAULT_APP_SPEC
        self.session: PfSession | None = None
        self.__device: Hook | None = None
        self.__convo: LastEvents = {}
        self.__active: Playback | None = None
        self.__buffer: PlaybackBuffer = []
        self.__sequence = itertools.count()
        self.__stream = None

    def streaming(self, *devices: InputStream):
        build(self.__app)

        tts_enabled = False
        for device in devices:

            if device.SESSIONIZER == STTSession:
                follow_policy(self.__app, RecognizerRepo(), ServiceTypes.STT) 

            elif device.SESSIONIZER == TTSSession:
                tts_enabled = True
                follow_policy(self.__app, SpeechRepo(), ServiceTypes.TTS)

        self.session = PfSession(*devices)

        if tts_enabled:
            device = Hook()
            self.session.add_device(device)
            self.__device = device

        return self.session

    def speech(self, text: str, voice: str, speed: int = 1):
        if not self.__device:
            raise RuntimeError(
                    "This session does not have a TTS worker running"
                    )
        self.__device.speak(text, voice, speed=speed)

    def print(self, event: PfEvent) -> None:
        print("\033[2J\033[H", end="")
        self.__convo[(event.service, event.device_id)] = event
        for identity, event in self.__convo.items():
            print("-" * 3, identity[0], identity[1], "-" * 3)
            print(event.recording.text + "\n")
        print("\n\n", "-" * 25)
        assert self.session
        for name, status in self.session.statuses.items():
            print(f"{name}: {status.line}")
        print("-" * 25, "\n\n")

    def play(self,
             event: PfEvent | None = None,
             priority: int = 10,
             kill: bool = False,
             ):
        assert self.session

        if kill:
            self.__buffer = []
            self.session.unmute()
            return

        if event:
            playback = Playback(
                        priority=priority,
                        sequence=next(self.__sequence),
                        waveform= event.recording.audio.to_waveform(),
                        samplerate=event.recording.audio.samplerate,
                        )
            heapq.heappush(self.__buffer, playback)
            self.__ensure_stream(playback.samplerate)


    def __callback(self, outdata, frames, *_):

        outdata.fill(0)

        if self.__active is None:
            if self.__buffer:
                self.__active = heapq.heappop(self.__buffer)
                if self.session:
                    self.session.mute()
            elif self.session:
                self.session.unmute()
            return

        elif self.__buffer:
            waiting = self.__buffer[0]
            if waiting < self.__active:
                heapq.heappush(self.__buffer, self.__active)
                self.__active = heapq.heappop(self.__buffer)

        start = self.__active.cursor
        stop = start + frames
        chunk = self.__active.waveform[start:stop]
        n = len(chunk)
        outdata[:n, 0] = chunk
        self.__active.cursor += n

        if self.__active.cursor >= len(self.__active.waveform):
            self.__active = None

    def __ensure_stream(self, samplerate: int):
        if self.__stream is not None:
            return
        self.__stream = sounddevice.OutputStream(
                samplerate=samplerate,
                channels=1,
                dtype="float32",
                callback=self.__callback,
                )
        self.__stream.start()

