import argparse

from pfspeak.common.defaults import DEFAULT_LLM


parser = argparse.ArgumentParser(prog="pfspeak")

sub = parser.add_subparsers(dest="command")

sub.add_parser("help")
sub.add_parser("config")
sub.add_parser("install")
sub.add_parser("listen")
sub.add_parser("speak")
sub.add_parser("test")
sub.add_parser("verify")
sub.add_parser("import-check")
parser.add_argument("--regenerate", action="store_true")

chat = sub.add_parser("chat", help="Run the local speech-to-speech assistant demo.")
chat.add_argument("--model", default=DEFAULT_LLM, metavar="MODEL", help="Ollama model to use (default: %(default)s).")
chat.add_argument("--voice", default="af_heart", metavar="VOICE", help="Kokoro voice to use for speech synthesis (default: %(default)s).")
chat.add_argument("--silence", type=float, default=5.0, metavar="SECONDS", help="Seconds of silence before automatically finalizing speech.")
chat.add_argument("--min-words", type=int, default=15, metavar="N", help="Minimum words required before sending speech to the language model.")
# chat.add_argument("--no-greeting", action="store_true", help="Disable the assistant greeting on startup.")
#chat.add_argument("--clear", action="store_true", help="Clear the terminal before starting.")

worker = sub.add_parser("worker")
worker.add_argument("--host", default="127.0.0.1")
worker.add_argument("--port", type=int, default=24024)
