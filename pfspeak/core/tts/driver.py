from pathlib import Path

from pfspeak.common import models
from .inference import SpeechModel
from collections.abc import Generator
from pfspeak.common.dataclasses import (
        PfToken,
        WorkerMessage,
        TokenList,
        )
from pfspeak.core.repos import SpeechRepo 
from pfspeak.common.defaults import AppSpec
from multiprocessing.connection import Connection
from pfspeak.common.types import AudioPrediction, Prediction


class Driver:

    @staticmethod
    def generate_from_string(phoneme_string: str,
                             model: SpeechModel,
                             voice: str,
                             speed: float,
                             ) -> Generator[AudioPrediction]:
        yield Driver.infer(model, phoneme_string, voice, speed) 

    @staticmethod
    def generate_from_tokens(tokens: TokenList,
                             model: SpeechModel,
                             voice: str,
                             speed: float = 1,
                             ) -> Generator[Prediction]:
        for token_batch in Driver.chunks(tokens, model.max_phonemes):
            prediction = Driver.infer(model, token_batch.phonemes, voice, speed)
            yield token_batch, prediction

    @staticmethod
    def infer(model: SpeechModel,
              phonemes: str, 
              voice: str,
              speed: float,
              ) -> AudioPrediction:

        if not len(phonemes):
            raise ValueError("phonemes cannot be empty")
        if speed <= 0:
            raise ValueError("speed must be greater than zero")

        return model(phonemes, voice, speed)

    @staticmethod
    def is_split_point(token: PfToken):
        return (
                token.phonemes is not None
                and token.phonemes != "'"
                and not token.phonemes.isalnum()
                )

    @staticmethod
    def chunks(tokens: TokenList, max_size: int) -> Generator[TokenList]:
        """
        Yield TokenLists containing at most `max_size` phoneme characters,
        preferring to split on punctuation when possible.

        Any algorithm that keeps chunks under the model limit would work.
        This one simply falls back to the last punctuation mark before the
        limit, otherwise it splits at the limit.
        """
        while len(tokens) > max_size:

            last_split_point = 0

            for i in range(tokens.count - 1):

                token = tokens[i]

                if Driver.is_split_point(token):
                    last_split_point = i

                if len(tokens[:i])> max_size:
                    split_at = last_split_point or i
                    yield tokens[:split_at]
                    tokens = tokens[split_at:]

                    break

        yield tokens

    @staticmethod
    def worker(app: AppSpec, repo: SpeechRepo, conn: Connection):
        model = SpeechModel(app, repo)
        model.load_model()
        while True:
            msg: WorkerMessage = conn.recv()
            for audio_prediction in Driver.generate_from_tokens(msg.tokens,
                                                                model,
                                                                msg.voice,
                                                                msg.speed):
                conn.send(audio_prediction)
