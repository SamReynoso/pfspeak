import os
import sys
import pickle
import socket
import subprocess
from time import sleep
from pfspeak.core.repo import SpeechRepo
from pfspeak.common.dataclasses import (
        Prediction,
        WorkerMessage,
        WorkerMessageBase)
from pfspeak.core.runtime.driver import Driver
from pfspeak.common.defaults import IPC_AUTHKEY
from pfspeak.common.defaults import DEFAULT_APP_SPEC 
from pfspeak.core.runtime.inference import SpeechModel
from multiprocessing.connection import Listener, Client
from multiprocessing import current_process


def worker(host: str, port: int):

    print(f"Worker pid={os.getpid()}")

    current_process().authkey = IPC_AUTHKEY

    conn = Listener((host, port), authkey=IPC_AUTHKEY).accept()

    repo = SpeechRepo()
    model = SpeechModel(DEFAULT_APP_SPEC, repo)
    model.load_model()

    while True:

        msg: WorkerMessage = conn.recv()

        if msg.op == "stop":
            print("Worker exited normally")
            return

        for audio_prediction in Driver.generate_from_tokens(msg.tokens,
                                                            model,
                                                            msg.voice,
                                                            msg.speed):
            pred = Prediction(
                        device_id=msg.device_id,
                        tokens=audio_prediction[0],
                        audio=audio_prediction[1][0],
                        pred_dur=audio_prediction[1][1]
                        )
            conn.send(pred)

def start():

    print(f"Session pid={os.getpid()}")

    current_process().authkey = IPC_AUTHKEY

    HOST, PORT, WORKER_ARGS = _prepare_worker_launch()

    child = subprocess.Popen([sys.executable, *WORKER_ARGS])

    for _ in range(50):
        try:
            conn = Client((HOST, PORT), authkey=IPC_AUTHKEY)
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

    print("Worker shutdown Normally")
