import heapq
import itertools
from uuid import UUID
from typing import Callable
from sounddevice import OutputStream
from pfspeak.core.runtime import worker
from pfspeak.extra.voices import Voices
from pfspeak.app.directories import build
from pfspeak.core.types import ServiceTypes
from pfspeak.core.param import ListenParams
from pfspeak.common.types import OptionalSpec
from pfspeak.common.g2p import Graphemes2Phonemes
from pfspeak.core.runtime.pipeline import WorkerAdapter
from pfspeak.common.dataclasses import PfEvent, Playback
from pfspeak.core.repo import RecognizerRepo, SpeechRepo
from pfspeak.core.devices import Devices, Hook, InputStream
from pfspeak.common.defaults import DEFAULT_APP_SPEC, AppSpec
from pfspeak.core.asset import RecognizerAsset, follow_policy
from pfspeak.core.session import PfSession, SttBackend, TtsBackend


LastEvents = dict[tuple[PfEvent.EventTypes, UUID], PfEvent]
PlaybackBuffer = list[Playback]

PfApp = Callable[[PfSession, PfEvent], None]

class PfSpeak:
    voices = Voices
    devices = Devices
    AppSpec = AppSpec

    def __init__(self, app: OptionalSpec = None) -> None:
        self.__app = app or DEFAULT_APP_SPEC
        self.session: PfSession | None = None
        self.__hook: Hook | None = None
        self.__convo: LastEvents = {}
        self.__active: Playback | None = None
        self.__buffer: PlaybackBuffer = []
        self.__sequence = itertools.count()
        self.__stream: OutputStream | None = None
        self.__print_lines: list[str] = []
        self.__cancel_playback = False

    def run(self, app: PfApp, *devices):
        with self.streaming(*devices) as session:
            for event in session:
                app(session, event)

    def streaming(self, *devices: InputStream) -> PfSession:
        build(self.__app)

        tts_enabled = False
        for device in devices:

            if SttBackend.is_compatiable(device):
                follow_policy(self.__app, RecognizerRepo(), ServiceTypes.STT) 

            elif TtsBackend.is_compatiable(device):
                tts_enabled = True
                follow_policy(self.__app, SpeechRepo(), ServiceTypes.TTS)

        g2p = Graphemes2Phonemes()
        worker_adapter = WorkerAdapter(worker.start)
        recognizer_asset = RecognizerAsset(DEFAULT_APP_SPEC, RecognizerRepo())
        recognizer = recognizer_asset.load(ListenParams())

        self.session = PfSession(g2p, worker_adapter, recognizer)
        self.session.add_devices(devices)

        if tts_enabled:
            device = Hook()
            self.session.add_device(device)
            self.__hook = device

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
        elif value.service != PfEvent.EventTypes.TICKET:
                assert value.service and value.device_id
                self.__convo[(value.service, value.device_id)] = value

        for identity, event in self.__convo.items():
            assert event.recording
            print(f"[{identity[0].upper()}]")
            print("\t" + event.recording.text + "\n")
            if event.service == event.types.STT:
                print("FINALIZED:", event.finalized)
            if event.status:
                print("STATUS:", event.status)
            print()

        print("\n\n", "-" * 25)
        for line in self.__print_lines:
            print(line)
        assert self.session

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
