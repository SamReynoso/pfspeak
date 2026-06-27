from pfspeak.common import models
from pfspeak.core.params import ListenParams
from pfspeak.common.types import OptionalSpec
from pfspeak.core.stt.buffer import ListenBuffer
from pfspeak.common.g2p import Graphemes2Phonemes
from pfspeak.core.stream import STTSession, TTSSession
from pfspeak.core.repos import RecognizerRepo, SpeechRepo
from pfspeak.core.stt.stream import AudioSource, Microphone
from pfspeak.common.defaults import DEFAULT_APP_SPEC, Voices


AudioType = type[AudioSource]


class TextToSpeech:

    def __init__(self,
                 app: OptionalSpec = None,
                 repo: SpeechRepo | None = None,
                 g2p: Graphemes2Phonemes | None = None,
                 ) -> None:
        self.app = app or DEFAULT_APP_SPEC
        self.repo = repo or SpeechRepo()
        self.g2p = g2p or Graphemes2Phonemes()


    def streaming(self) -> TTSSession:
        return TTSSession(self.app, self.repo, self.g2p)


class SpeechToText:

    def __init__(self,
                 app: OptionalSpec = None,
                 repo: RecognizerRepo | None = None,
                 params: ListenParams | None = None,
                 g2p: Graphemes2Phonemes | None = None,
                 ) -> None:

        self.app = app or DEFAULT_APP_SPEC
        self.repo = repo or RecognizerRepo()
        self.params = params or ListenParams()
        self.g2p = g2p or Graphemes2Phonemes()

        self.results = []

    def streaming(self, device: AudioType = Microphone) -> STTSession:
        recognizer = models.recognizer(self.app, self.repo, self.params)
        buffer = ListenBuffer(recognizer, self.g2p)
        instance = device(self.params, callback_factory=buffer.callback_factory)
        return STTSession(instance, buffer)


class PfSpeak:


    def __init__(self, app: OptionalSpec = None) -> None:
        self.app = app or DEFAULT_APP_SPEC
        self.stt = SpeechToText(app=app)
        self.tts = TextToSpeech(app=app)

        # self.download = 
        self.prepare = Prepare(self)


class Prepare:

    def __init__(self, instance: PfSpeak) -> None:
        self.__pfspeak = instance
        self.speech = None
        self.listen = None

    def prepare_speech(self, fn):
        self.speech = fn
        return fn

    def prepare_listen(self):
        ...
    
