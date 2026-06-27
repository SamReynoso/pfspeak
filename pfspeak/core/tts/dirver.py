from pfspeak.common import Output, Result, TokenList, models
from pfspeak.common.dataclasses import PipelineCmds
from pfspeak.common.defaults import AppSpec
from pfspeak.common.just_checking import TypeTensor
from pfspeak.core.repos import SpeechRepo 

from .inference import SpeechModel

from typing import Callable, Generator, List, Union
from multiprocessing.connection import Connection


class Driver:

    @staticmethod
    def generate_from_string(phoneme_string: str, model, pack, speed):
        if len(phoneme_string) > 510:
            m = f'Phoneme string too long: {len(phoneme_string)} > 510'
            raise ValueError(m)
        yield Driver.infer(model, phoneme_string, pack, speed) 

    @staticmethod
    def generate_from_tokens(tokens: TokenList,
                             model: SpeechModel,
                             voice: str,
                             speed: float = 1,
                             ) -> Generator[Result]:
        pack = model.load_voice(voice)
        for ts in Driver.chunks(tokens):
            output = Driver.infer(model, ts.phonemes, pack, speed)
            result = Result(
                    tokens=ts,
                    waveform=model.cast_waveform(output),
                    )
            result.join_timestamps(output.pred_dur)
            yield result

    @staticmethod
    def infer(
            model: SpeechModel,
            phonemes: str, 
            pack: TypeTensor,
            speed: Union[float, Callable[[int], float]] = 1
            ) -> Output:
        if len(phonemes) > 510:
            raise ValueError("Phoneme string length > 510")
        if callable(speed):
            speed = speed(len(phonemes))
        
        return model(phonemes,
                     pack[len(phonemes)-1],
                     speed,
                     return_output=True
                     )

    @staticmethod
    def waterfall_last(tokens: TokenList,
                       next_count: int,
                       waterfall: List[str] = ['!.?…', ':;', ',—'],
                       bumps: List[str] = [')', '”']
                       ) -> int:
        for w in waterfall:
            z = next(
                    (i for i, t in reversed(list(enumerate(tokens)))
                     if t.phonemes in set(w)), None
                    )
            if z is None:
                continue
            z += 1
            if z < len(tokens) and tokens[z].phonemes in bumps:
                z += 1
            if next_count - len(tokens[:z]) <= 510:
                return z
        return len(tokens)

    @staticmethod
    def chunks(tokens: TokenList) -> Generator[TokenList]:
        processed = TokenList()
        phoneme_count = 0

        for token in tokens:
            if token.phonemes is None:
                continue
            token_size = len(token.phonemes) + len(token.whitespace)
            if phoneme_count + token_size > 510:
                split_at = Driver.waterfall_last(tokens,
                                                 phoneme_count + token_size
                                                 )
                yield processed[:split_at]
                processed = processed[split_at:]
                phoneme_count = len(processed)
            processed.append(token)
            phoneme_count += token_size
        if processed:
            yield processed


    @staticmethod
    def worker(app: AppSpec, repo: SpeechRepo, conn: Connection):
        model = models.inference_model(app, repo)
        model.load_model()
        while True:
            cmd: PipelineCmds | bool = conn.recv()
            if cmd is False or cmd is True:
                return
            for ret in Driver.generate_from_tokens(cmd.tokens,
                                                   model,
                                                   cmd.voice,
                                                   cmd.speed):
                conn.send(ret)
            conn.send(False)
