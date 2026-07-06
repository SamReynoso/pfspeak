import sys
from pfspeak import PfSpeak
from pfspeak.core import Fifo


DESCRIPTION = "FIFO named pipe text-to-speech example"


def main() -> int:
    pf = PfSpeak()

    try:
        fifo = Fifo("./input.pipe")
    except Exception:
        sys.stderr.write("FIFO: Could not get file descriptor\n")
        return 1

    try:

        with pf.streaming(fifo) as session:
            print("FIFO: System Ready...")
            for event in session:
                pf.play(event)

    except KeyboardInterrupt:
        print('FIFO: shutdown requested')
        return 0
    except Exception:
        sys.stderr.write("\nFIFO: shutdown requested\n")
        return 1

    print("FIFO: goodbye")
    return 0
