from pfspeak.core.asset import follow_policy
from pfspeak.core.repo import RecognizerRepo, SpeechRepo
from pfspeak.core.session import PfSession, STTSession, TTSSession
from pfspeak.core.devices import InputStream
from pfspeak.common.types import OptionalSpec
from pfspeak.common.g2p import Graphemes2Phonemes
from pfspeak.common.defaults import DEFAULT_APP_SPEC, AppSpec

from pfspeak.core.types import ServiceTypes
from pfspeak.extra.voices import Voices
from pfspeak.core.devices import Devices


class PfSpeak:

    voices = Voices
    devices = Devices
    AppSpec = AppSpec

    def __init__(self, app: OptionalSpec = None) -> None:
        self.app = app or DEFAULT_APP_SPEC
        self.g2p = Graphemes2Phonemes()

    def streaming(self, *devices: InputStream):
        for device in devices:
            if device.SESSIONIZER == STTSession:
                follow_policy(self.app, RecognizerRepo(), ServiceTypes.STT) 
            elif device.SESSIONIZER == TTSSession:
                follow_policy(self.app, SpeechRepo(), ServiceTypes.TTS)
        return PfSession(*devices)
