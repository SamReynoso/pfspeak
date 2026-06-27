from .dirver import Driver
from .inference import SpeechModel
from multiprocessing import Pipe, Process
from pfspeak.common.g2p import Graphemes2Phonemes
from pfspeak.common.defaults import AppSpec, RepoSpec
from typing import Callable, Generator, TypeAlias, Union
from pfspeak.common.dataclasses import PipelineCmds, Result, TokenList


DifferedDef: TypeAlias = Union[Callable, None]
VoidableDef: TypeAlias = Union[Callable, None]


class PfPipeline:

    def __init__(self,
                 app: AppSpec,
                 repo: RepoSpec,
                 g2p: Graphemes2Phonemes
                 ) -> None:
        self.app = app
        self.repo = repo
        self.g2p = g2p
        self._child = None
        self._parent_conn = None

    def start_worker(self):
        parent, child = Pipe()

        self._child = Process(
                target=Driver.worker,
                args=(
                    self.app,
                    self.repo,
                    child
                    )
                )

        self._child.start()
        self._parent_conn = parent

    def send(self, tokens: TokenList, voice: str, speed: float = 1) -> None:
        assert self._parent_conn
        self._parent_conn.send(
                PipelineCmds(
                    op="speak",
                    tokens=tokens,
                    voice=voice,
                    speed=speed
                    )
                )

    def recv(self) -> Result | bool:
        assert self._parent_conn
        return self._parent_conn.recv()

    def stop(self):
        assert self._parent_conn and self._child
        self._parent_conn.send(True)
        self._child.join()

    def __call__(self,
                 text: str,
                 voice: str,
                 lang: str | None = None,
                 speed: float = 1,
                 ) -> Generator[Result]:

        tokens = self.g2p(text, lang=lang)
        self.send(tokens, voice, speed)
        while True:
            cmd = self.recv()
            if cmd is False or cmd is True:
                break
            yield cmd
