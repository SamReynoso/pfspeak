from pathlib import Path

from pfspeak.common import models
from pfspeak.core import params
from pfspeak.core.stream import Session
from pfspeak.core.stt import buffer
from collections.abc import Generator
from pfspeak.common.dataclasses import Result
from pfspeak.core.tts.pipeline import PfPipeline
from pfspeak.core.stt.buffer import ListenBuffer
from pfspeak.common.g2p import Graphemes2Phonemes
from pfspeak.core.tts.inference import SpeechModel
from pfspeak.core.repos import RecognizerRepo, SpeechRepo
from pfspeak.core.params import ListenParams, SpeechParams
from pfspeak.core.stt.stream import AudioSource, Microphone
from pfspeak.common.defaults import DEFAULT_APP_SPEC, AppSpec, Voices



OptionalSpec = AppSpec | None
PfGenerator = Generator[Result, None, bool]


class TextToSpeech:

    repo = SpeechRepo()
    g2p = Graphemes2Phonemes()

    def __init__(self, app: OptionalSpec = None) -> None:
        self.app = app or DEFAULT_APP_SPEC
        model = models.inference_model(self.app, self.repo)
        self.pipeline = PfPipeline(model, self.g2p)

    def say(self, text: str, voice: str, **kwargs) -> PfGenerator:
        local_dir = self.repo.local_dir(self.app) 
        voice_filename = self.repo.voice_weights_filename(voice)
        for result in self.pipeline(text, local_dir / voice_filename, **kwargs):
            yield result
        return False


AudioType = type[AudioSource]

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

    def streaming(self, device: AudioType = Microphone) -> Session:
        recognizer = models.recognizer(self.app, self.repo, self.params)
        buffer = ListenBuffer(recognizer, self.g2p)
        instance = device(self.params, callback_factory=buffer.callback_factory)
        return Session(instance, buffer)


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
    
