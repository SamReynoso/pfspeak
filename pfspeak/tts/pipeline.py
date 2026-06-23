from pathlib import Path
from multiprocessing import Pipe, Process

from pfspeak.common.g2p import Graphemes2Phonemes

from .model import SpeechModel
from .specs import ModelParams
from .dirver import Driver

from pfspeak.common.dataclasses import PipelineCmds, Result
from typing import Callable, Dict, Generator, TypeAlias, Union


DifferedDef: TypeAlias = Union[Callable, None]
VoidableDef: TypeAlias = Union[Callable, None]


class PfPipeline:

    def __init__(self):
        self.model: SpeechModel = SpeechModel()
        self.g2p: Graphemes2Phonemes = Graphemes2Phonemes()

        self._child = None
        self._parent_conn = None

    def load_model(self, params: ModelParams) -> None:
        self.model.with_params(params) 
        self.model.load_weights()
        self.model.to_device()
        self.model.to_inference_mode()

    def load_g2p(self, **kwargs):
        self.g2p.load(**kwargs)

    def start_worker(self, params, g2p_params):
        parent, child = Pipe()
        self._child = Process(
                target=PfPipeline.worker,
                args=(
                    params,
                    g2p_params,
                    child,
                    )
                )
        self._child.start()
        self._parent_conn = parent

    def start(self, params: ModelParams, g2p_params: Dict)  -> None:
        self.load_model(params)
        self.load_g2p(**g2p_params)

    @classmethod
    def worker(cls, params, g2p_params, conn):
        instance = cls()
        instance.start(params, g2p_params)
        instance.runforever(conn)

    def send(self,
             text: str,
             voice: Path,
             lang: str | None = None,
             speed: float = 1
             ) -> None:
        assert self._parent_conn
        self._parent_conn.send(
                PipelineCmds(
                    op="speak",
                    text=text,
                    voice=voice,
                    lang=lang,
                    speed=speed
                    )
                )

    def recv(self) -> Result:
        assert self._parent_conn
        return self._parent_conn.recv()

    def stop(self):
        assert self._parent_conn and self._child
        self._parent_conn.send(PipelineCmds(op="stop", text="", voice=Path()))
        self._child.join()

    def runforever(self, conn):
        while True:
            cmds: PipelineCmds = conn.recv()
            match cmds.op:
                case 'stop':
                    return
                case 'speak':
                    for result in self.generate(
                            text=cmds.text,
                            voice_path=cmds.voice,
                            lang=cmds.lang,
                            speed=cmds.speed,
                            ):
                        conn.send(result)

    def generate(self,
                 text: str,
                 voice_path: Path,
                 lang: str | None = None,
                 speed: float = 1,
                 ) -> Generator[Result]:
        tokens = self.g2p(text, lang=lang, voice_path=voice_path)
        pack = self.model.load_voice(voice_path)
        yield from Driver.generate_from_tokens(tokens, self.model, pack, speed)

    def __call__(self,
                 text: str,
                 voice: Path,
                 lang: str | None = None,
                 speed: float = 1,
                 ) -> Result:
        return Result.join(self.generate(text, voice, lang=lang, speed=speed))

def resolve_speed_options(text: str,
                          speed: float | None = None,
                          speed_fn: VoidableDef = None,
                          ) -> float:
    if speed:
        return speed
    if speed_fn:
        return speed_fn(text)
    return 1
