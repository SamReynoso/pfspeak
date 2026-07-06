from typing import Callable
from subprocess import Popen
from threading import Thread
from multiprocessing import Queue
from multiprocessing.connection import Connection
from pfspeak.common.dataclasses import WorkRequest, Sentinel


PopWorker = Callable[..., tuple[Popen, Connection]]

class WorkerAdapter:
    def __init__(self, start: PopWorker):
        self._start = start

    def start(self):
        self.child, self.conn = self._start()


class PipelineConnections:
    def __init__(self,
                 worker: WorkerAdapter,
                 add_prediction: Callable,
                 exceptions: Queue,
                 ) -> None:
        self.worker = worker
        self.keep_alive = True
        self.exceptions = exceptions
        self.request_queue = Queue()
        self.add_prediction = add_prediction
        self.send_out = self._as_thread(self.__send_out)
        self.receive_back = self._as_thread(self.__receive_back)

    def _as_thread(self, job):
        def with_exception_handling():
            try:
               job() 
            except Exception as e:
                self.exceptions.put(e)
        return Thread(target=with_exception_handling, daemon=True)

    def __send_out(self):
        while self.keep_alive:
            self.worker.conn.send(self.request_queue.get())

    def __receive_back(self):
        while self.keep_alive:
            self.add_prediction(self.worker.conn.recv())

    def factory(self):
        def callback(request: WorkRequest):
            self.request_queue.put(request)
        return callback

    def join(self):
        self.keep_alive = False
        self.request_queue.put(Sentinel())

    def start(self):
        self.worker.start()
        self.send_out.start()
        self.receive_back.start()
