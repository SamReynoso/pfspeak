from typing import Callable
from functools import wraps


def architecture_initialized(fn):
    @wraps(fn)
    def wrapper(self, *args, **kwargs):
        from pfspeak.core.architecture.architecture import KokoroArchitecture
        import torch
        if self.arch is None:
            if self.params is None:
                raise RuntimeError(
                        "Attemting to initiate Architecture without module "
                        "parameters"
                        )
            self.arch = KokoroArchitecture(self.params)
            self.torch = torch
        return fn(self, *args, **kwargs)
    return wrapper


def torch_imported(fn):
    @wraps(fn)
    def wrapper(self, *args, **kwargs):
        if self.torch is None:
            import torch
            self.torch = torch
        return fn(self, *args, **kwargs)
    return wrapper


def start_on_call(fn: Callable):
    """ Strat the pipeline if it has not already been started """
    def decorator(self, *args, **kwargs):
        if not self._pipeline_started:
            self.pipeline.start(self.model_params, self.g2p_kwargs)
            self._pipeline_started = True
        return fn(self, *args, **kwargs)
    return decorator
