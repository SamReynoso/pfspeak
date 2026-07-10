from pathlib import Path
from typing import Iterable, List
from pfspeak.core.param import G2PParams
from pfspeak.common.types import VoidableDef
from pfspeak.vendors import en_misaki, espeak_misaki
from pfspeak.common.just_checking import TypeMToken
from pfspeak.common.dataclasses import PfToken, TokenList
from pfspeak.common.defaults import LANG_CODES, ALIASES
from pfspeak.common.exceptions import LanguageNotImplemented, MisakiImportError


def lang_code_or_raise(lang_code):
    lang_code = lang_code.lower()
    lang_code = ALIASES.get(lang_code, lang_code)
    assert lang_code in LANG_CODES, (lang_code, LANG_CODES)
    return lang_code


def infer_lang_code_from_voice_path(voice_path: Path):
    code = str(voice_path).split("/")[-1][0]
    assert code in ["a", "b"], code
    return code


def infer_lang_code_from_voice_label(voice_label: str):
    code = voice_label[0]
    assert code in ["a", "b"], code
    return code


class Graphemes2Phonemes:

    def __init__(self) -> None:
        self._cached_backends = {}
        self._en_callable: VoidableDef = None
        self.load(G2PParams())

    def load(self,
             spec: G2PParams | None = None,
             trf: bool | None = None,
             version: str | None = None,
             default_lang: str | None = None,
             en_callable: VoidableDef = None,
             ) -> None:
        if spec:
            self.trf=spec.trf
            self.version=None
            self.default_lang=spec.default_lang
            self.en_callable=en_callable
        if trf:
            self.trf = trf
        if version:
            self.version = version
        if en_callable:
            self.en_callable = en_callable
        if default_lang:
            self.default_lang = default_lang

    def ensure(self, code: str):
        self.get(code).warmup()

    def get(self, code: str):
        lang = lang_code_or_raise(code)
        if lang not in self._cached_backends:
            self._cached_backends[lang] = self.create_back_end(lang)
        return self._cached_backends[lang]


    def create_back_end(self, code: str):
        try:
            print(f"Creating graphemem to phoneme backend: code({code})")
            if code in ("a", "b"):
                british = code == "b"
                try:
                    fallback = espeak_misaki.EspeakFallback(british=british)
                except Exception:
                    fallback = None
                g2p = en_misaki.G2P(
                        trf=self.trf,
                        british=british,
                        fallback=fallback,
                        unk="")
            else:
                match code:
                    case "j":
                        from misaki import ja
                        g2p = ja.JAG2P()
                    case "z":
                        from misaki import zh
                        g2p = zh.ZHG2P(
                                version=self.version,
                                en_callable=self.en_callable
                                )
                    case _:
                        language = LANG_CODES[code]
                        g2p = espeak.EspeakG2P(language=language)
            return g2p

        except ImportError as e:
            raise MisakiImportError(lang_code=code) from e
        except KeyError:
            raise LanguageNotImplemented(lang_code=code)

    @staticmethod
    def misaki_to_token_list(mtokens: Iterable[TypeMToken]) -> TokenList:
        tokens: List[PfToken] = [
                PfToken(
                    text=t.text,
                    phonemes=t.phonemes,
                    whitespace=t.whitespace,
                    start_time=t.start_ts,
                    ) 
                for t in mtokens
                ]
        return TokenList(tokens)

    def __call__(self,
                 text: str,
                 lang: str | None = None,
                 ):
        code = lang 
        if not code:
            code = self.default_lang
        assert code is not None, "code was none but should have been some"
        if code in ("a", "b"):
            tokens = self.misaki_to_token_list(self.get(code)(text)[1])
        else:
            # TODO: Put TokenList tokenizer here non English
            # TODO: Really
            raise LanguageNotImplemented(lang_code=code)
        return tokens
