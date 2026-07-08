import os
import sys
import socket
import subprocess
from time import sleep
from subprocess import Popen
from collections import deque
from pfspeak.core.repo import SpeechRepo
from pfspeak.common.dataclasses import (
        Prediction,
        Sentinel,
        TokenList,
        WorkRequest)
from multiprocessing import current_process
from pfspeak.core.runtime.driver import Driver
from pfspeak.common.defaults import IPC_AUTHKEY
from multiprocessing.connection import Connection
from pfspeak.common.just_checking import TypeTensor
from pfspeak.common.defaults import DEFAULT_APP_SPEC 
from pfspeak.core.runtime.inference import SpeechModel
from multiprocessing.connection import Listener, Client


PopWorkerOutput = tuple[Popen, Connection]




def worker(host: str, port: int):

    print(f"TTS worker: pid={os.getpid()}")

    current_process().authkey = IPC_AUTHKEY

    conn = Listener((host, port), authkey=IPC_AUTHKEY).accept()

    repo = SpeechRepo()
    model = SpeechModel(DEFAULT_APP_SPEC, repo)
    model.load_model()

    jobs: deque[WorkRequest] = deque()

    gen = None
    current_job = None

    while True:

        if conn.poll(timeout=.02):
            message: WorkRequest | Sentinel = conn.recv()
            if isinstance(message, Sentinel):
                conn.send(message)
                print("TTS worker: shutting down")
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

            audio, prediction_duration = Driver.infer(model,
                                                      chunk.phonemes,
                                                      current_job.voice,
                                                      current_job.speed
                                                      )

            apply_prediction_duration_timestamps(chunk, prediction_duration)

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
            gen = Driver.chunks(current_job.tokens, 254)



def start() -> PopWorkerOutput:

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


def shutdown(process):

    try:
        process.wait(timeout=2)
        print("TTS worker: shutdown normally")
    except subprocess.TimeoutExpired:
        process.terminate()
        process.wait(timeout=2)
        print("TTS worker: terminated")


def apply_prediction_duration_timestamps(
        tokens: TokenList,
        prediction_duration: TypeTensor
        ) -> None:
    """
    Attach timestamps to each token using the model's predicted durations.

    Walk the predicted durations from left to right. Trailing whitespace is
    split evenly between the current token and the next token.
    """

    if len(prediction_duration) < 3:
        return

    frames_per_second = 80
    next_start = max(0, prediction_duration[0].item() - 3) * 2
    index = 1

    for token in tokens:

        if index >= len(prediction_duration) - 1:
            break

        if not token.phonemes:
            if token.whitespace:
                index += 1
                next_start += prediction_duration[index].item() * 2
                index += 1
            continue

        phoneme_end = index + len(token.phonemes)

        if phoneme_end >= len(prediction_duration):
            break

        token.start_time = next_start / frames_per_second
        token_duration = prediction_duration[index:phoneme_end].sum().item() * 2
        token_end = next_start + token_duration
        index = phoneme_end

        if token.whitespace:
            half_whitespace = prediction_duration[phoneme_end].item()
            token_end += half_whitespace
            next_start = token_end + half_whitespace
            index += 1
        else:
            next_start = token_end

        token.end_time = token_end / frames_per_second
