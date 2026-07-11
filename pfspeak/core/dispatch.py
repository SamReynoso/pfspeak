from typing import Callable

from pfspeak.common.dataclasses import PfEvent
from pfspeak.core.devices import InputStream
from pfspeak.core.session import PfSession


class AppDispatch:

    def __init__(self) -> None:
        self.devices = {}
        self.__handlers = {}
        self.__every = None

    def every(self, fn: Callable):
        self.__every = fn
        return fn

    def text(self, device: InputStream):
        if device.service != "tts":
            raise ValueError(
                    "Device handler registration for 'text' event must be a "
                    "tts device"
                    )
        self.devices[device.device_id] = device
        def wrapper(fn: Callable):
            self.__handlers[("text", device.device_id, False)] = fn
            return fn
        return wrapper

    def tts(self, device: InputStream):
        if device.service != "tts":
            raise ValueError(
                    "Device handler registration for 'tts' event must be a "
                    "tts device"
                    )
        self.devices[device.device_id] = device
        def wrapper(fn: Callable):
            self.__handlers[("tts", device.device_id, True)] = fn
            return fn
        return wrapper

    def partial(self, device: InputStream):
        if device.service != "stt":
            raise ValueError(
                    "Device handler registration for 'partial' event must be a "
                    "stt device"
                    )
        self.devices[device.device_id] = device
        def wrapper(fn: Callable):
            self.__handlers[("stt", device.device_id, False)] = fn
            return fn
        return wrapper

    def final(self, device: InputStream):
        if device.service != "stt":
            raise ValueError(
                    "Device handler registration for 'final' event must be a "
                    "stt device"
                    )
        self.devices[device.device_id] = device
        def wrapper(fn: Callable):
            self.__handlers[("stt", device.device_id, True)] = fn
            return fn
        return wrapper

    def duck(self, device: InputStream):
        if device.service != "stt":
            raise ValueError(
                    "Device handler registration for 'stt' event must be a "
                    "tts device"
                    )
        self.devices[device.device_id] = device
        def wrapper(fn: Callable):
            self.__handlers[("duck", device.device_id, True)] = fn
            return fn
        return wrapper

    def __call__(self, session: PfSession, event: PfEvent):
        if self.__every:
            self.__every(session, event)
        identity = (event.service, event.device_id, event.finalized)
        if handler := self.__handlers.get(identity):
            handler(session, event)
