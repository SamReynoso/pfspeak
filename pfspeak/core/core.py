from pfspeak.core.session import PfSession
from pfspeak.core.sources import InputStream
from pfspeak.common.types import OptionalSpec
from pfspeak.common.g2p import Graphemes2Phonemes
from pfspeak.common.defaults import DEFAULT_APP_SPEC

class PfSpeak:

    def __init__(self, app: OptionalSpec = None) -> None:
        self.app = app or DEFAULT_APP_SPEC
        self.g2p = Graphemes2Phonemes()

    def streaming(self, *devices: InputStream):
        return PfSession(list(devices))
