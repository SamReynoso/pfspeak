from .inference import SpeechModel
from collections.abc import Generator
from pfspeak.common.dataclasses import (
        PfToken,
        TokenList,
        )
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
            current = 0

            for i , token in enumerate(tokens):

                current += len(token)

                if current > max_size:
                    split_at = last_split_point or i
                    yield tokens[:split_at]
                    tokens.tokens = tokens.tokens[split_at:]
                    break


                if Driver.is_split_point(token):
                    last_split_point = i

        yield tokens
