from pathlib import Path
from typing import Callable, Union
from pfspeak.extra.voices import VoiceEnum
from pfspeak.common.defaults import AppSpec
from pfspeak.common.just_checking import NDArray, Float32 
from pfspeak.common.dataclasses import AudioChunk, Recording


PathLike = Path | str
Waveform = NDArray[Float32]
VoiceLable = VoiceEnum | str
OptionalSpec = AppSpec | None
WaveformBuffer = list[Waveform]
DifferedDef = Union[Callable, None]
VoidableDef = Union[Callable, None]
Recordings = Recording | list[Recording]
AudioCallback = Callable[[AudioChunk], None]
CallbackFactory = Callable[[int], AudioCallback] 
