import argparse

from pfspeak.common.defaults import DEFAULT_LLM


parser = argparse.ArgumentParser(prog="pfspeak")

sub = parser.add_subparsers(dest="command")

sub.add_parser("help")
sub.add_parser("config")
sub.add_parser("daemon")

examples = sub.add_parser("examples", help="PfSpeak Example and Demonstrations.")
examples.add_argument("example", choices=["chat", "stt", "fifo"])

chat = sub.add_parser("chat", help="Run the local speech-to-speech assistant demo.")

worker = sub.add_parser("worker")
worker.add_argument("--host", default="127.0.0.1")
worker.add_argument("--port", type=int, default=24024)
