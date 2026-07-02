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
    child = None
    conn = None

    def __init__(self,
                 send_to,
                 receive_back,
                 ) -> None:
        self.send_to = Thread(target=send_to, daemon=True)
        self.receive_back = Thread(target=receive_back, daemon=True)

    def start(self):
        print("Pipeline: initualizing connectons")
        self.child, self.conn = worker.start()
        self.send_to.start()
        self.receive_back.start()

    def close(self):
        assert self.child
        worker.shutdown(self.conn, self.child)
        self.send_to.join()
        self.receive_back.join()
        print("Pipeline: works shutdown")

    def send(self, value):
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
        print("Pipeline: inistulizing ")
        self.app = app
        self.repo = repo
        self.g2p = g2p


        self.buffer = Queue()
        self.status = PfStatus()
        self.add_event: DifferedDef = None

        self.speed = 1
        self.voice = Voices.EN.AF_HEART
        self.connections = PipelineConnections(self.send_to, self.receive_back)
        print("Pipeline: initualized")

    def __update_status(self, message: WorkerMessage):
        self.status.sent += len(message.tokens)

    def __post_recording(self, prediction: Prediction):
        assert self.add_event
        self.status.received+= len(prediction.tokens)
        self.add_event(prediction.event(self.status))

    def send_to(self):
        while self.streaming:
            msg: WorkerMessage | Sentinel = self.buffer.get()
            self.connections.send(msg)
            if isinstance(msg, Sentinel):
                return
            self.__update_status(msg)

    def receive_back(self):
        assert self.add_event
        while self.streaming:
            prediction: Prediction = self.connections.recv()
            self.__post_recording(prediction)

    def start(self):
        print("Pipeline: starting")
        self.streaming = True
        self.connections.start()
        print("Pipeline: READY")

    def stop(self):
        print("Pipeline: stopping")
        self.streaming = False
        self.buffer.put(Sentinel())
        self.connections.close()
        print("Pipeline: stopped")

    def factory(self):
        print("Pipeline: Device assigned")

        def callback(request: WorkRequest):
            voice = self.voice if request.voice is None else request.voice
            message = request.make(self.g2p(request.text), voice=voice)
            assert self.add_event
            self.buffer.put(message)

        return callback
