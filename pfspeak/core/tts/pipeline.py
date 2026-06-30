import numpy
from queue import Queue
from .driver import Driver
from threading import Thread
from pfspeak.common.dataclasses import (
        Audio,
        TokenList,
        Recording,
        AudioChunk,
        WorkerMessage,
        )
from multiprocessing import Pipe, Process
from pfspeak.core.repos import SpeechRepo
from pfspeak.common.g2p import Graphemes2Phonemes
from pfspeak.common.defaults import AppSpec, Voices
from pfspeak.common.types import DifferedDef, Prediction
from pfspeak.common.dataclasses import PfEvent, PfStatus


def to_recording(prediction: Prediction):
    tokens = prediction[0]
    waveform = numpy.array(prediction[1][0]).astype(numpy.float32)
    chunk = AudioChunk(waveform=waveform,
                       samplerate=24_000,
                       start_time=0)
    return Recording(tokens=tokens, audio=Audio([chunk])) 


class PipelineConnections:
    child = None
    conn = None

    def __init__(self,
                 send_from_buffer,
                 drain_forever,
                 start_worker,
                 ) -> None:
        self.send_from_buffer = Thread(target=send_from_buffer, daemon=True)
        self.drain_forever = Thread(target=drain_forever, daemon=True)
        self.start_worker = start_worker

    def start(self):
        self.child, self.conn = self.start_worker()
        self.send_from_buffer.start()
        self.drain_forever.start()

    def close(self):
        assert self.child
        self.child.join()
        self.send_from_buffer.join()
        self.drain_forever.join()

    def send(self, value):
        print("sending")
        print(value)
        assert self.conn
        self.conn.send(value)

    def recv(self):
        assert self.conn
        return self.conn.recv()


class PfPipeline:

    def __init__(self,
                 app: AppSpec,
                 repo: SpeechRepo,
                 g2p: Graphemes2Phonemes
                 ) -> None:
        self.app = app
        self.repo = repo
        self.g2p = g2p

        self.streaming = False
        self.connections = PipelineConnections(
                self.send_from_buffer,
                self.drain_forever,
                self.start_worker,
                )

        self.buffer = Queue()
        self.status = PfStatus()
        self.add_event: DifferedDef = None

        self.voice = Voices.AF_HEART
        self.speed = 1

    def start_worker(self):
        parent_conn, child_conn = Pipe()

        child = Process(
                target=Driver.worker,
                args=(
                    self.app,
                    self.repo,
                    child_conn
                    )
                )

        child.start()
        return child, parent_conn

    def send_from_buffer(self):
        while self.streaming:
            tokens = self.buffer.get()
            self.send(tokens, self.voice, speed=self.speed)

    def update_status_on_send(self, tokens: TokenList):
        self.status.sent += len(tokens)

    def message_sent_event(self, tokens: TokenList):
        assert self.add_event
        self.add_event(
                PfEvent(
                    service=PfEvent.Service.TTS,
                    status=self.status,
                    recording=None
                    )
                )

    def send(self, tokens: TokenList, voice: str, speed: float = 1) -> None:
        self.update_status_on_send(tokens)
        print(tokens)
        self.connections.send(
                WorkerMessage(
                    op="speak",
                    tokens=tokens,
                    voice=voice,
                    speed=speed
                    )
                )
        self.message_sent_event(tokens)

    def update_status_on_receive(self, tokens: TokenList):
        self.status.received += len(tokens)

    def drain_forever(self):
        while self.streaming:
            prediction: Prediction = self.connections.recv()
            self.update_status_on_receive(prediction[0])
            assert self.add_event
            self.add_event(
                    PfEvent(
                        service=PfEvent.Service.TTS,
                        status=self.status,
                        recording=to_recording(prediction)
                        )
                    )

    def factory(self):

        def callback(text):

            tokens = self.g2p(text)
            assert self.add_event
            self.buffer.put(tokens)


        return callback

    def start(self):
        self.streaming = True
        self.connections.start()

    def stop(self):
        self.streaming = False
        self.connections.close()
