
from misaki import en, espeak

from pfspeak.common.defaults import LANG_CODES


def get_g2p_for_lang(lang_code: str,
                     version: str | None = None,
                     trf = None,
                     en_callable = None
                     ):
    try:
        if lang_code in 'ab':
            british = lang_code == 'b'
            try:
                fallback = espeak.EspeakFallback(british=british)
            except Exception as e:
                fallback = None
            g2p = en.G2P(trf=trf, british=british, fallback=fallback, unk='')

        else:
            match lang_code:
                case 'j':
                    from misaki import ja
                    g2p = ja.JAG2P()
                case 'z':
                    from misaki import zh
                    g2p = zh.ZHG2P(version= version, en_callable=en_callable)
                case _:
                    language = LANG_CODES[lang_code]
                    g2p = espeak.EspeakG2P(language=language)
        return g2p

    except ImportError as e:
        raise ImportError(f"Misaki Import Error: lan_code: {lang_code}") from e
    except KeyError as e:
        raise KeyError(f"Language Code Error: {lang_code}") from e
