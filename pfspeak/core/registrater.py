
from typing import Callable


class CallableRegister:

    def __init__(self) -> None:
        self._en_callable = None
        self._speed= None

    @property
    def en_callable(self):
        return self._en_callable

    def set_en_callable(self, fn: Callable | None):
        if fn is not None:
            self._en_callable = fn
            return fn
        def decorator(fn: Callable):
            self._en_callable = fn
            return fn
        return decorator

    @property
    def speed(self):
        return self._speed

    def set_speed(self, fn: Callable | None):
        if fn is not None:
            self._speed = fn
            return fn
        def decorator(fn: Callable):
            self._speed = fn
            return fn
        return decorator


