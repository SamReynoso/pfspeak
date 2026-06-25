from pathlib import Path
from multiprocessing import Pipe, Process

from pfspeak.common.g2p import Graphemes2Phonemes

from .inference import SpeechModel
from .dirver import Driver

from pfspeak.common.dataclasses import PipelineCmds, Result
from typing import Callable, Generator, TypeAlias, Union


DifferedDef: TypeAlias = Union[Callable, None]
VoidableDef: TypeAlias = Union[Callable, None]


class PfPipeline:

    def __init__(self,
                 inference_model: SpeechModel,
                 g2p_backend: Graphemes2Phonemes
                 ):
        self.model = inference_model
        self.g2p = g2p_backend
        self._child = None
        self._parent_conn = None

    @classmethod
    def worker(cls,
               inference_mode: SpeechModel,
               g2p_backend: Graphemes2Phonemes,
               conn):
        instance = cls(inference_mode, g2p_backend)
        instance.runforever(conn)

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
            for result in self.__call__(
                    text=cmds.text,
                    voice_path=cmds.voice,
                    lang=cmds.lang,
                    speed=cmds.speed,
                    ):
                conn.send(result)

    def __call__(self,
                 text: str,
                 voice_path: Path,
                 lang: str | None = None,
                 speed: float = 1,
                 ) -> Generator[Result]:

        tokens = self.g2p(text, lang=lang, voice_path=voice_path)
        pack = self.model.load_voice(voice_path)
        yield from Driver.generate_from_tokens(tokens, self.model, pack, speed)
