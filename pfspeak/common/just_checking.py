from __future__ import annotations
from typing import TYPE_CHECKING, Iterable, TypeAlias, Any


"""


 Reserved: Doc String


"""

if TYPE_CHECKING:
    from misaki.en import MToken as TypeMToken
    from pfspeak.tts.architecture import KokoroArchitecture as TypeArchitecture

    from sherpa_onnx import OnlineRecognizer as TypeRecognizer

    from torch import Tensor as TypeTensor
    from numpy import float32 as Float32
    from numpy.typing import NDArray

else:
    TypeMToken: TypeAlias = Any
    TypeArchitecture: TypeAlias = Any

    TypeRecognizer: TypeAlias = Any

    TypeTensor: TypeAlias = Any
    Float32: TypeAlias = Any
    NDArray: TypeAlias = Iterable


__all__ = [
        "TypeTensor",
        "TypeArchitecture",
        "Float32",
        "NDArray",
        "TypeMToken",
        "TypeRecognizer",
        ]


