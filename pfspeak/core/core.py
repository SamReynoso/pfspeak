import sounddevice
from collections import deque
from pfspeak.extra.voices import Voices
from pfspeak.app.directories import build
from pfspeak.core.types import ServiceTypes
from pfspeak.core.asset import follow_policy
from pfspeak.core.devices import InputStream
from pfspeak.common.types import OptionalSpec
from pfspeak.core.devices import Devices, Hook
from pfspeak.extra.concatenate import concatenate
from pfspeak.core.repo import RecognizerRepo, SpeechRepo
from pfspeak.common.dataclasses import PfEvent, TokenList
from pfspeak.common.defaults import DEFAULT_APP_SPEC, AppSpec
from pfspeak.core.session import PfSession, STTSession, TTSSession


class PfSpeak:

    voices = Voices
    devices = Devices
    AppSpec = AppSpec

    def __init__(self, app: OptionalSpec = None) -> None:
        self.__app = app or DEFAULT_APP_SPEC
        self.session: PfSession | None = None
        self.__device: Hook | None = None
        self.__sd_stream = None
        self.buffer = deque()
        self.samplerates = deque()

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


    def play(self, event: PfEvent | None = None, kill: bool = False):
        if kill:
            sounddevice.stop()
            self.buffer = deque()
            return

        if event:
            self.buffer.append(concatenate(event.recording.audio)[0].waveform)
            self.samplerates.append(event.recording.audio.samplerate)

        if self.__sd_stream:
            if self.__sd_stream.active:
                print("skipping while stream is active")
                return

        if not self.buffer:
            return 

        waveform = self.buffer.popleft()
        samplerate = self.samplerates.popleft()
        sounddevice.play(waveform, samplerate=samplerate)
        self.__sd_stream = sounddevice.get_stream()

    def print(self, event: PfEvent, clear: int = False) -> None:
        if clear:
            print("\033[2J\033[H", end="")

        tokens = event.recording.tokens

        if len(event.recording.text):
            print("-" * 32) 
            line = TokenList()
            for token in tokens:
                if len(line) < 64:
                    line.append(token)
                else:
                    print(line.text)
                    line = TokenList()
            if line:
                print(line.text)
