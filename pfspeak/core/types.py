from enum import StrEnum


class ServiceTypes(StrEnum):
    TTS = "tts"
    STT = "stt"


class LoadPolicy(StrEnum):
    EAGER = "eager"
    LAZY = "lazy"
