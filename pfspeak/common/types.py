from pathlib import Path
from typing import Callable, Union
from pfspeak.common.defaults import AppSpec
from pfspeak.common.just_checking import NDArray, Float32, TypeTensor
from pfspeak.common.dataclasses import TokenList, AudioChunk



type PathLike = Path | str
type AudioPrediction = tuple[TypeTensor, TypeTensor]
type Prediction = tuple[TokenList, AudioPrediction]
type OptionalSpec = AppSpec | None
type Waveform = NDArray[Float32]
type WaveformBuffer = list[Waveform]
type DifferedDef = Union[Callable, None]
type VoidableDef = Union[Callable, None]
type AudioCallback = Callable[[AudioChunk], None]
type CallbackFactory = Callable[[int], AudioCallback] 




