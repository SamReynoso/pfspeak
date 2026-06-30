import argparse


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

worker = sub.add_parser("worker")
worker.add_argument(
    "--host",
    default="127.0.0.1",
)
worker.add_argument(
    "--port",
    type=int,
    default=24024,
)

parser.add_argument(
    "--regenerate",
    action="store_true",
)
