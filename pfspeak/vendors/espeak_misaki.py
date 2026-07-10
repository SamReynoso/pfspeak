
### BEGIN ###
def set_espeak_library():
    # https://github.com/bootphon/phonemizer/issues/44#issuecomment-1540885186
    from phonemizer.backend.espeak.wrapper import EspeakWrapper
    if not EspeakWrapper._ESPEAK_LIBRARY:
        import os
        import platform
        library = dict(
            Darwin='/opt/homebrew/Cellar/espeak-ng/1.52.0/lib/libespeak-ng.1.dylib',
            Windows='C:\\Program Files\\eSpeak NG\\libespeak-ng.dll',
        ).get(platform.system())
        if library and os.path.exists(library):
            EspeakWrapper.set_library(library)
    return EspeakWrapper._ESPEAK_LIBRARY

#### END ####

import re

# EspeakFallback is used as a last resort for English
class EspeakFallback:
    E2M = sorted({
        'ʔˌn\u0329':'tn', 'ʔn\u0329':'tn', 'ʔn':'tn', 'ʔ':'t',
        'a^ɪ':'I', 'a^ʊ':'W',
        'd^ʒ':'ʤ',
        'e^ɪ':'A', 'e':'A',
        't^ʃ':'ʧ',
        'ɔ^ɪ':'Y',
        'ə^l':'ᵊl',
        'ʲo':'jo', 'ʲə':'jə', 'ʲ':'',
        'ɚ':'əɹ',
        'r':'ɹ',
        'x':'k', 'ç':'k',
        'ɐ':'ə',
        'ɬ':'l',
        '\u0303':'',
    }.items(), key=lambda kv: -len(kv[0]))

    def __init__(self, british):
        set_espeak_library()
        import phonemizer
        self.british = british
        self.backend = phonemizer.backend.EspeakBackend(
            language=f"en-{'gb' if british else 'us'}",
            preserve_punctuation=True, with_stress=True, tie='^'
        )

    def __call__(self, token):
        ps = self.backend.phonemize([token.text])
        if not ps:
            return None, None
        ps = ps[0].strip()
        for old, new in type(self).E2M:
            ps = ps.replace(old, new)
        ps = re.sub(r'(\S)\u0329', r'ᵊ\1', ps).replace(chr(809), '')
        if self.british:
            ps = ps.replace('e^ə', 'ɛː')
            ps = ps.replace('iə', 'ɪə')
            ps = ps.replace('ə^ʊ', 'Q')
        else:
            ps = ps.replace('o^ʊ', 'O')
            ps = ps.replace('ɜːɹ', 'ɜɹ')
            ps = ps.replace('ɜː', 'ɜɹ')
            ps = ps.replace('ɪə', 'iə')
            ps = ps.replace('ː', '')
        ps = ps.replace('o', 'ɔ') # for espeak < 1.52
        return ps.replace('^', ''), 2

# EspeakG2P used for most non-English/CJK languages
class EspeakG2P:
    E2M = sorted({
        'a^ɪ':'I', 'a^ʊ':'W',
        'd^z':'ʣ', 'd^ʒ':'ʤ',
        'e^ɪ':'A',
        'o^ʊ':'O', 'ə^ʊ':'Q',
        's^s':'S',
        't^s':'ʦ', 't^ʃ':'ʧ',
        'ɔ^ɪ':'Y',
    }.items())

    def __init__(self, language):
        self.language = language
        self.backend = phonemizer.backend.EspeakBackend(
            language=language, preserve_punctuation=True, with_stress=True,
            tie='^', language_switch='remove-flags'
        )

    def __call__(self, text):
        # Angles to curly quotes
        text = text.replace('«', chr(8220)).replace('»', chr(8221))
        # Parentheses to angles
        text = text.replace('(', '«').replace(')', '»')
        ps = self.backend.phonemize([text])
        if not ps:
            return ''
        ps = ps[0].strip()
        for old, new in type(self).E2M:
            ps = ps.replace(old, new)
        # Delete any remaining tie characters, hyphens (not sure what they mean)
        ps = ps.replace('^', '').replace('-', '')
        # Angles back to parentheses
        ps = ps.replace('«', '(').replace('»', ')')
        return ps
