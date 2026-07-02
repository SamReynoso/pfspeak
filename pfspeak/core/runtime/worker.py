import os
import sys
import socket
import subprocess
from time import sleep, time
from collections import deque
from pfspeak.core.repo import SpeechRepo
from pfspeak.common.dataclasses import (
        Prediction,
        WorkerMessage,
        WorkerMessageBase)
from multiprocessing import current_process
from pfspeak.core.runtime.driver import Driver
from pfspeak.common.defaults import IPC_AUTHKEY
from pfspeak.common.defaults import DEFAULT_APP_SPEC 
from pfspeak.core.runtime.inference import SpeechModel
from multiprocessing.connection import Listener, Client


def worker(host: str, port: int):

    print(f"TTS worker: pid={os.getpid()}")

    current_process().authkey = IPC_AUTHKEY

    conn = Listener((host, port), authkey=IPC_AUTHKEY).accept()

    repo = SpeechRepo()
    model = SpeechModel(DEFAULT_APP_SPEC, repo)
    model.load_model()

    jobs: deque[WorkerMessage] = deque()

    gen = None
    current_job = None

    while True:

        if conn.poll(timeout=.02):
            message = conn.recv()
            if message.op == "stop":
                print("TTS worker: exited normally")
                return
            if current_job and current_job.device_id == message.device_id:
                current_job.tokens.tokens += message.tokens.tokens
            else:
                jobs.append(message)

        if gen is not None:
            assert current_job

            try:

                chunk = next(gen)

            except StopIteration:
                gen, current_job = None, None
                continue

            inferance_start = time()
            audio, prediction_duration = Driver.infer(model,
                                                      chunk.phonemes,
                                                      current_job.voice,
                                                      current_job.speed
                                                      )

            print(f"Worker: inference took {time() - inferance_start} seconds")

            conn.send(
                    Prediction(
                        audio=audio,
                        tokens=chunk,
                        pred_dur=prediction_duration,
                        device_id=current_job.device_id,
                        )
                      )
        elif jobs:
            current_job = jobs.popleft()
            gen = Driver.chunks(current_job.tokens, model.max_phonemes)


def start():

    print(f"Main: pid={os.getpid()}")

    current_process().authkey = IPC_AUTHKEY

    host, port, worker_args = _prepare_worker_launch()

    child = subprocess.Popen([sys.executable, *worker_args])

    for _ in range(50):
        try:
            conn = Client((host, port), authkey=IPC_AUTHKEY)
            break
        except ConnectionRefusedError:
            sleep(0.05)
    else:
        raise ConnectionRefusedError

    return child, conn


def _prepare_worker_launch():

    host = "127.0.0.1"
    _sock = socket.socket()
    _sock.bind((host, 0))
    port = _sock.getsockname()[1]
    _sock.close()

    args = "-m", "pfspeak", "worker","--host", host, "--port", str(port)
    return host, port, args


def shutdown(conn, process):

    conn.send(WorkerMessageBase(op="stop"))

    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.terminate()
        process.wait(timeout=2)

    print("TTS worker: shutdown Normally")
