from pfspeak.core.session import PfSession
from pfspeak.core.devices import InputStream
from pfspeak.common.types import OptionalSpec
from pfspeak.common.g2p import Graphemes2Phonemes
from pfspeak.common.defaults import DEFAULT_APP_SPEC, AppSpec

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
        return PfSession(*devices)
