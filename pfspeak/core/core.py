import heapq
import itertools
from uuid import UUID
from typing import Callable
from time import monotonic_ns
from threading import Thread, Event
from sounddevice import OutputStream
from pfspeak.core.runtime import worker
from pfspeak.extra.voices import Voices
from pfspeak.app.directories import build
from pfspeak.core.session import PfSession
from contextlib import asynccontextmanager
from pfspeak.core.types import ServiceTypes
from pfspeak.core.param import ListenParams
from pfspeak.common.types import OptionalSpec
from pfspeak.core.dispatch import AppDispatch
from pfspeak.common.g2p import Graphemes2Phonemes
from pfspeak.core.devices import Hook, InputStream
from pfspeak.common.defaults import DEFAULT_APP_SPEC
from pfspeak.common.dataclasses import PfEvent, Playback
from pfspeak.core.repo import RecognizerRepo, SpeechRepo
from pfspeak.core.asset import RecognizerAsset, follow_policy


LastEvents = dict[tuple[PfEvent.EventTypes, UUID], PfEvent]
PlaybackBuffer = list[Playback]
PfApp = Callable[[PfSession, PfEvent], None] | AppDispatch


class PfSpeak:
    voices = Voices

    def __init__(self, app: OptionalSpec = None) -> None:
        self.__app = app or DEFAULT_APP_SPEC
        self.__hook: Hook | None = None
        self.__convo: LastEvents = {}
        self.__active: Playback | None = None
        self.__buffer: PlaybackBuffer = []
        self.__sequence = itertools.count()
        self.__stream: OutputStream | None = None
        self.__print_lines: list[str] = []
        self.__cancel_playback = False
        self.__dispatch = AppDispatch()
        self.__ready = Event()

        self.session: PfSession | None = None
        self.devices: dict[UUID, InputStream] = {}

    def run(self, app: PfApp | None = None, *devices: InputStream):
        app = app or self.__dispatch
        if isinstance(app, AppDispatch):
            devices = tuple(app.devices.values())
        if not devices:
            raise ValueError("Can't start session without at least one device")
        with self.streaming(*devices) as session:
            for event in session:
                app(session, event)

    def every(self, fn):
        return self.__dispatch.every(fn)

    def text(self, device: InputStream):
        return self.__dispatch.text(device)

    def tts(self, device: InputStream):
        return self.__dispatch.tts(device)

    def partial(self, device: InputStream):
        return self.__dispatch.partial(device)

    def final(self, device: InputStream):
        return self.__dispatch.final(device)

    def duck(self, device: InputStream):
        return self.__dispatch.duck(device)

    def hook(self, fn: Callable):
        if self.__hook is None:
            self.__hook = Hook()
        decorator = self.__dispatch.tts(self.__hook)
        return decorator(fn)

    def start(self, *args):
        self.__thread = Thread(target=self.run, args=args, daemon=True)
        self.__thread.start()
        self.__ready.wait()

    def stop(self):
        if self.__stream:
            self.__stream.stop()
        if self.session:
            self.session.shutdown()
        if self.__thread:
            self.__thread.join()
        self.session = None
        self.__thread = None

    def streaming(self, *devices: InputStream) -> PfSession:
        build(self.__app)

        tts_enabled, stt_enabled = False, False
        for device in devices:
            if device.service is ServiceTypes.STT and not tts_enabled:
                tts_enabled = True
                follow_policy(self.__app, SpeechRepo(), ServiceTypes.TTS)
                if stt_enabled:
                    break
            if device.service is ServiceTypes.TTS and not tts_enabled:
                tts_enabled = True
                follow_policy(self.__app, RecognizerRepo(), ServiceTypes.STT) 
                if stt_enabled:
                    break

        g2p = Graphemes2Phonemes()
        recognizer_asset = RecognizerAsset(DEFAULT_APP_SPEC, RecognizerRepo())
        recognizer = recognizer_asset.load(ListenParams())
        self.session = PfSession(g2p, worker.start, recognizer)

        for device in devices:
            self.devices[device.device_id] = device
            self.session.add_device(device)

        if tts_enabled:
            if self.__hook is None:
                self.__hook = Hook()
            if self.__hook.device_id not in self.session.devices:
                self.session.add_device(self.__hook)

        self.__ready.set()  # go
        return self.session

    def say(self, text: str, voice: str, speed: int = 1) -> None:
        if not self.__hook:
            msg = "This session does not have a TTS worker running"
            raise RuntimeError(msg)
        self.__hook.voice = voice
        self.__hook.speed = speed
        self.__hook.adapter(text)

    def print(self, value: PfEvent | str) -> None:
        print("\033[2J\033[H", end="")
        if isinstance(value, str):
            self.__print_lines.append(value)
        elif value.recording:
                assert value.service and value.device_id
                self.__convo[(value.service, value.device_id)] = value
        screen = ""

        for identity, event in self.__convo.items():
            assert event.recording, event
            screen += f"[{identity[0].upper()}]\n\t{event.recording.text}\n"
            if event.service == event.types.STT:
                screen += f"FINALIZED: {event.finalized}\n"
            if event.status:
                screen += f"STATUS:, {event.status}\n"
            screen += (
                    "AGE: "
                    f"{monotonic_ns() - event.recording.audio.created_ns}ns"
                    "\n"
                    "MODIFIED: "
                    f"{monotonic_ns() - event.recording.audio.modified}ns"
                    "\n"
                    )

        screen += "\n\n" + "-" * 25 + "\n"
        for device in self.devices.values():
            screen += device.status.name + ":\n"
            for line in device.status.lines:
                screen += "\t" + line + "\n"

        screen += "\n\n" + "-" * 25 + "\n"
        for line in self.__print_lines:
            screen += line + "\n"
        print(screen)


    def play(self,
             event: PfEvent | None = None,
             priority: int = 10,
             kill: bool = False,
             ) -> None:
        assert self.session

        if kill:
            self.__cancel_playback = True
            return

        if event and event.recording:

            try:
                waveform = event.recording.to_waveform()
            except ValueError:
                raise ValueError("Failed to create waveform from recording")

            playback = Playback(
                        priority=priority,
                        sequence=next(self.__sequence),
                        waveform= waveform,
                        samplerate=event.recording.audio.samplerate)

            heapq.heappush(self.__buffer, playback)
            self.__ensure_stream(playback.samplerate)


    def __callback(self, outdata, frames, *_) -> None:

        assert self.session

        if self.__cancel_playback:
            self.__active = None
            self.__buffer = []
            self.session.stt.unmute()
            return

        outdata.fill(0)

        if self.__active and self.__buffer and self.__active > self.__buffer[0]:
            active = heapq.heappop(self.__buffer)
            heapq.heappush(self.__buffer, self.__active)
            self.__active = active

        elif self.__active is None and self.__buffer:
            self.__active = heapq.heappop(self.__buffer)
            self.session.stt.mute()

        elif self.__active is None:
            return

        assert self.__active
        start = self.__active.cursor
        stop = start + frames
        chunk = self.__active.waveform[start:stop]
        n = len(chunk)
        outdata[:n, 0] = chunk
        self.__active.cursor += n

        if self.__active.cursor >= len(self.__active.waveform):
            self.__active = None
            self.session.stt.unmute()

    def __ensure_stream(self, samplerate: int) -> None:
        if self.__stream is not None:
            return
        self.__stream = OutputStream(
                samplerate=samplerate,
                channels=1,
                dtype="float32",
                callback=self.__callback)

        self.__stream.start()

    @asynccontextmanager
    async def lifespan(self, _):
        self.start()
        try:
            yield
        finally:
            self.stop()
