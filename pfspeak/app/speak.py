import sys
from pfspeak import PfSpeak
from pfspeak.core import Fifo


def serve() -> int:
    pf = PfSpeak()

    try:
        fifo = Fifo("./input.pipe")
    except Exception:
        sys.stderr.write("Could not get file descriptor\n")
        return 1

    try:

        with pf.streaming(fifo) as session:
            print("System Ready...")
            for event in session:
                pf.play(event)

    except KeyboardInterrupt:
        sys.stderr.write("\nshutdown requested\n")
        print('shutdown_requested')
        return 0
    except Exception:
        print('unexpected error')
        return 1

    return 0
