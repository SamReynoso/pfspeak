from queue import Queue
from threading import Thread
from pfspeak.extra.voices import Voices
from pfspeak.core.runtime import worker
from pfspeak.core.repo import SpeechRepo
from pfspeak.common.defaults import AppSpec
from pfspeak.common.types import DifferedDef
from pfspeak.common.g2p import Graphemes2Phonemes
from pfspeak.common.dataclasses import WorkRequest, WorkerMessage
from pfspeak.common.dataclasses import Sentinel, PfStatus, Prediction


class PipelineConnections:

    def __init__(self, send_out, receive_back) -> None:
        self.receive_back = Thread(target=receive_back, daemon=True)
        self.send_out = Thread(target=send_out, daemon=True)
        self.conn = None
        self.child = None

    def start(self):
        print("Pipeline: initualizing connectons")
        self.child, self.conn = worker.start()
        self.receive_back.start()
        self.send_out.start()

    def close(self):
        assert self.child
        worker.join(self.child)
        self.receive_back.join()
        self.send_out.join()
        print("Pipeline: works shutdown")

    @property
    def send(self):
        assert self.conn
        return self.conn.send

    @property
    def recv(self):
        assert self.conn
        return self.conn.recv


class PfPipeline:

    def __init__(self,
                 app: AppSpec,
                 repo: SpeechRepo,
                 g2p: Graphemes2Phonemes
                 ) -> None:
        print("Pipeline: inistulizing ")
        self.app = app
        self.repo = repo
        self.g2p = g2p


        self.buffer = Queue()
        self.status = PfStatus()
        self.add_event: DifferedDef = None

        self.speed = 1
        self.voice = Voices.EN.AF_HEART
        self.connections = PipelineConnections(self.send_out, self.receive_back)
        print("Pipeline: initualized")

    def __update_status(self, message: WorkerMessage):
        self.status.sent += len(message.tokens)

    def __post_recording(self, prediction: Prediction):
        assert self.add_event
        self.status.received+= len(prediction.tokens)
        self.add_event(prediction.event(self.status))

    def send_out(self):
        while True:
            msg: WorkerMessage | Sentinel = self.buffer.get()
            self.connections.send(msg)
            if isinstance(msg, Sentinel):
                return
            self.__update_status(msg)

    def receive_back(self):
        assert self.add_event
        while True:
            prediction: Prediction | Sentinel = self.connections.recv()
            if isinstance(prediction, Sentinel):
                return
            self.__post_recording(prediction)

    def start(self):
        print("Pipeline: starting")
        self.connections.start()
        print("Pipeline: READY")

    def stop(self):
        print("Pipeline: stopping")
        self.buffer.put(Sentinel())
        self.connections.close()
        print("Pipeline: stopped")

    def factory(self):
        print("Pipeline: device assigned")

        def callback(request: WorkRequest):
            voice = self.voice if request.voice is None else request.voice
            message = request.make(self.g2p(request.text), voice=voice)
            self.buffer.put(message)

        return callback
