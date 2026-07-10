from queue import Queue
from typing import Callable
from subprocess import Popen
from threading import Thread
from pfspeak.common.defaults import SENTINEL
from multiprocessing.connection import Connection
from pfspeak.common.dataclasses import PfStatus, Prediction, Sentinel, WorkRequest


PopWorker = Callable[..., tuple[Popen, Connection]]

class Marshal:
    def __init__(self,
                 start: PopWorker,
                 submit_event: Callable,
                 submit_exceptions: Callable,
                 ) -> None:
        self.request_queue: Queue[WorkRequest|Sentinel] = Queue()
        self.submit_exceptions = submit_exceptions
        self.submit_event = submit_event
        self.status = PfStatus(name="Marshal")
        self.__start = start
        self.__keep_alive = True
        self.__producer_thread = self.__as_thread(self.__producer)
        self.__consumer_thread = self.__as_thread(self.__consumer)

    def start(self):
        _, self.__conn = self.__start()
        self.__producer_thread.start()
        self.__consumer_thread.start()

    def stop(self):
        self.request_queue.put(SENTINEL)
        self.__producer_thread.join()
        self.__consumer_thread.join()

    def __as_thread(self, job):
        def with_exception_handling():
            try:
               job() 
            except Exception as e:
                self.submit_exceptions(e)
        return Thread(target=with_exception_handling, daemon=True)

    def __producer(self):
        while self.__keep_alive:
            request = self.request_queue.get()
            if request is SENTINEL:
                self.__keep_alive = False
            self.status.add("marchaling")
            self.__conn.send(request)

        self.status.add("producer thread closing")

    def __consumer(self):
        while self.__keep_alive:
            message: Prediction|Sentinel = self.__conn.recv()
            if isinstance(message, Sentinel):
                assert self.__keep_alive is False
                continue
            self.status.add("prediction received")
            self.submit_event(message.as_event())

        self.status.add("consumer thread closing")

    def __call__(self, value: WorkRequest):
        self.status.add("processing TSS")
        self.request_queue.put(value)
