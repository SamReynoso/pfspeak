from queue import Queue
from typing import Callable
from subprocess import Popen
from threading import Thread
from pfspeak.common.defaults import SENTINEL
from multiprocessing.connection import Connection
from pfspeak.common.dataclasses import Prediction, Sentinel


PopWorker = Callable[..., tuple[Popen, Connection]]

class WorkerAdapter:
    def __init__(self, start: PopWorker):
        self._start = start

    def start(self):
        self.child, self.conn = self._start()


class PipelineConnections:
    def __init__(self,
                 worker: WorkerAdapter,
                 submit_event: Callable,
                 submit_exceptions: Callable,
                 ) -> None:
        self.worker = worker
        self.keep_alive = True
        self.submit_exceptions = submit_exceptions
        self.request_queue = Queue()
        self.submit_event = submit_event
        self.send_out = self.__as_thread(self.__send_out)
        self.receive_back = self.__as_thread(self.__receive_back)

    def __as_thread(self, job):
        def with_exception_handling():
            try:
               job() 
            except Exception as e:
                self.submit_exceptions(e)
        return Thread(target=with_exception_handling, daemon=True)

    def __send_out(self):
        while self.keep_alive:
            self.worker.conn.send(self.request_queue.get())

    def __receive_back(self):
        while self.keep_alive:
            message: Prediction | Sentinel = self.worker.conn.recv()
            if isinstance(message, Sentinel):
                self.keep_alive = False
                return
            self.submit_event(message.as_event())

    def join(self):
        self.request_queue.put(SENTINEL)

    def start(self):
        self.worker.start()
        self.send_out.start()
        self.receive_back.start()
