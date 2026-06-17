from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pfspeak.core.model import PfModel
    from torch import Tensor

import json
from pathlib import Path

from pfspeak.core.specs import ModelSpec, RuntimeSpec
from pfspeak.core.defaults import ALIASES, LANG_CODES
from typing import (
        Any,
        Callable,
        Generator,
        List,
        Optional,
        Union,
        )
from pfspeak.core.dataclasses import Output, PipelineCmds, Result, TokenList

from pathlib import Path
from typing import Any, Optional



class Driver:

    @staticmethod
    def generate_from_string(phoneme_string: str, model, pack, speed):
        if len(phoneme_string) > 510:
            m = f'Phoneme string too long: {len(phoneme_string)} > 510'
            raise ValueError(m)
        output = Driver.infer(model, phoneme_string, pack, speed) 
        yield Result(phoneme_string=phoneme_string,
                     audio=output.audio)

    @staticmethod
    def generate_from_tokens(tokens: TokenList,
                             model: PfModel,
                             voice: Tensor,
                             speed: float = 1,
                             ) -> Generator[Result]:
        pack = voice.to(model.device)
        for ts in Driver.chunks(tokens):
            result = Driver.infer(model, ts.phonemes, pack, speed)
            result.tokens = ts
            yield result

    @staticmethod
    def infer(
            model: PfModel,
            phoneme_string: str,
            pack: Tensor,
            speed: Union[float, Callable[[int], float]] = 1
            ) -> Result:
        if not phoneme_string:
            raise
        elif len(phoneme_string) > 510:
            phoneme_string = phoneme_string[:510]
        if callable(speed):
            speed = speed(len(phoneme_string))
        
        model_output: Output = model(phoneme_string,
                                     pack[len(phoneme_string)-1],
                                     speed,
                                     return_output=True
                                     )
        return Result(phoneme_string=phoneme_string,
                      audio=model_output.audio,
                      prediction_duration=model_output.pred_dur,
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



class PfPipeline:

    def __init__(self, config: RuntimeSpec):

        self.trf = config.trf
        self.kokoro_version = config.kokoro_version
        self.default_device = config.device
        self.lang_code = config.default_lang

        self.model: Any | None= None
        self.load_voice: Callable | None = None

        self.speed: Callable[[str], float] | None = None
        self.en_callable: Callable | None = None
        self.voices = {}
        self._g2p = {}

        self.model_loaded: bool = False
            

    def set_lang(self, lang_code: str):
        self.lang_code = lang_code_or_raise(lang_code)

    def load_g2p(self, code: str):
        lang = lang_code_or_raise(code)
        if not lang in self._g2p:
            self._g2p[lang] = get_g2p_for_lang(lang,
                                               self.kokoro_version,
                                               trf=self.trf,
                                               en_callable=self.en_callable)
    def g2p(self, text: str, voice: str | None = None, lang: str | None = None):
        code = None
        if voice and not lang:
            code = infer_lang_code_from_voice(voice)
        elif lang and not voice:
            code = lang
        elif not voice and not lang:
            code = self.lang_code
        else:
            raise RuntimeError(
                    "Calling g2p with both 'voice' and 'lang' is ambiguous"
                    )
        assert code is not None, "code was none but should have been some"
        self.load_g2p(code)
        ret = self._g2p[code](text)
        # NOTE: this is where I sould put the TokenList Tokenizer
        return ret

    def _warn_for_language_voice_mismatch(self, voice):
        if not voice.startswith(self.lang_code):
            v = LANG_CODES.get(voice, voice)
            p = LANG_CODES.get(self.lang_code, self.lang_code)
            raise RuntimeError(f"{v} with {p}")

    def load_model(self, model_spec: ModelSpec):
        import torch
        from pfspeak.core.model import PfModel

        def load_voice(voice_label: Path) -> Tensor:
            if voice_label in self.voices:
                return self.voices[voice_label]
            self.voices[voice_label] = torch.load(voice_label,
                                                  weights_only=True
                                                  )
            return self.voices[voice_label]

        self.model = init_model_or_raise(PfModel,
                                         model_spec,
                                         self.default_device
                                         )
        self.model.load_model(model_spec.model_path)
        self.load_voice = load_voice

        self.model_loaded = True

    def send(self, conn, cmds: PipelineCmds):
        conn.send(cmds.model_dump_json())

    def recv(self, conn):
        return PipelineCmds(**json.loads(conn.recv()))

    def run_forever(self, conn):

        assert self.model
        while True:
            cmds: PipelineCmds = self.recv(conn)

            match cmds.op:
                case 'stop':
                    break
                case 'speak':
                    for result in self.generate(cmds):
                        conn.send(result)

    def generate(self, cmds: PipelineCmds) -> Any:
        if self.model is None or self.load_voice is None:
            raise RuntimeError("Call load model with a model spec.")

        assert cmds.text

        if not cmds.speed:
            if self.speed:
                speed = self.speed(cmds.text)
            else:
                speed = 1
        else:
            speed = cmds.speed

        if cmds.lang:
            lang_code = cmds.lang
        else:
            lang_code = infer_lang_code_from_voice(cmds.voice)
        if lang_code in 'ab':
            x, tokens = self.g2p(cmds.text, lang=cmds.lang)
            print(x, "this is en g2p return x, _")
            assert isinstance(tokens, list)
            tokens = TokenList(tokens=tokens)
        else:
            raise # yield from non_en_process()

        pack = self.load_voice(cmds.voice,).to(self.model.device)
        yield from Driver.generate_from_tokens(tokens,
                                               self.model,
                                               pack,
                                               speed)

    def __call__(self, cmds: PipelineCmds) -> Result:
        return Result.join(self.generate(cmds))


def init_model_or_raise(model_class, config, device):
    try:
        return model_class(config=config).to(device).eval()
    except RuntimeError as e:
        if device == 'cuda':
            raise RuntimeError(f"Failed to initialize model on CUDA: {e}.") 
        raise


def device_available_or_raise(device, torch):
    match device:
        case 'cuda':
            if not torch.cuda.is_available():
                raise RuntimeError("CUDA requested but not available")
        case 'mps':
            if not torch.backends.mps.is_available():
                raise RuntimeError("MPS requested but not available")
        case None:
            device = 'cpu'
            if torch.cuda.is_available():
                device = 'cuda'
            elif torch.backends.mps.is_available():
                device = 'mps'
        case _:
            if device != 'cpu':
                raise RuntimeError(f"Unknown device type: {device}")
    return device


def lang_code_or_raise(lang_code):
    lang_code = lang_code.lower()
    lang_code = ALIASES.get(lang_code, lang_code)
    assert lang_code in LANG_CODES, (lang_code, LANG_CODES)
    return lang_code

def infer_lang_code_from_voice(voice_label):
    code = str(voice_label).split("/")[-1][0]
    assert code in ["a", "b"], code
    return code


def get_g2p_for_lang(lang_code: str,
                     version: Optional[str],
                     trf = None,
                     en_callable = None
                     ):
    british = lang_code == 'b'
    from misaki import en, espeak
    try:
        if lang_code in 'ab':
            try:
                fallback = espeak.EspeakFallback(british=british)
            except Exception as e:
                fallback = None
            g2p = en.G2P(trf=trf, british=british, fallback=fallback, unk='')
        elif lang_code == 'j':
                from misaki import ja
                g2p = ja.JAG2P()
        elif lang_code == 'z':
                from misaki import zh
                g2p = zh.ZHG2P(version= version, en_callable=en_callable)
        else:
            language = LANG_CODES[lang_code]
            g2p = espeak.EspeakG2P(language=language)
        return g2p
    except ImportError:
        if lang_code == 'z':
            m = "You need to `pip install misaki[zh]` to use lang_code='z'"
        else:
            m = "You need to `pip install misaki[ja]` to use lang_code='j'"
        raise ImportError(m)
