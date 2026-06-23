import time

from pfspeak import SpeechToText
from pfspeak.common.dataclasses import Result


if __name__ == "__main__":
    START = time.time()
    runtime = SpeechToText()

    @runtime.on_partial
    def on_partial(ret: Result):
        print(ret.text)

    @runtime.on_final
    def on_final(ret: Result):
        print(ret.text)

    @runtime.kill_on
    def kill_on() -> bool:
        diff = time.time() - START
        if diff > 5:
            return True
        return False

    runtime.runforever()
