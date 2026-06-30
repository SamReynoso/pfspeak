from pathlib import Path
from typing import Callable, Union
from pfspeak.common.defaults import AppSpec
from pfspeak.common.just_checking import NDArray, Float32, TypeTensor
from pfspeak.common.dataclasses import TokenList, AudioChunk, Recording


PathLike = Path | str
OptionalSpec = AppSpec | None
Waveform = NDArray[Float32]
WaveformBuffer = list[Waveform]
DifferedDef = Union[Callable, None]
VoidableDef = Union[Callable, None]
Recordings = Recording | list[Recording]
AudioCallback = Callable[[AudioChunk], None]
AudioPrediction = tuple[TypeTensor, TypeTensor]
Prediction = tuple[TokenList, AudioPrediction]
CallbackFactory = Callable[[int], AudioCallback] 
