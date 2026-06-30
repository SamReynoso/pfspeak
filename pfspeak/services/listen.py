import sys
import time

from pfspeak import SpeechToText
from queue import Queue
from threading import Thread

commands = Queue()

def fw(text: str):
    los = 0
    for word in text.split():
        if los >= 60:
            los = 0
        if los == 0:
            sys.stdout.write("\n\t")
        sys.stdout.write(f"{word} ")
        los += len(word) + 1
    sys.stdout.flush()

def keyboard():
    while True:
        cmd = input()
        if not cmd != []:
            cmd = "foobar"
        commands.put(cmd)


def listen(**_):

    stt = SpeechToText()

    Thread(target=keyboard, daemon=True).start()

    val = ""
    with stt.streaming() as session:
        while val.upper() != "EXIT":
            print(f"""\x1b[2J\x1b[H
    Commands:
    (any key + ENTER) commit partioals to the final area
    (exit + ENTER) to exit.

    Bonus:
    (speak)

{"-" * 40}
    FINAL
""", end="")

            for recording in session.recordings:
                fw(recording.text)
                print()

            print(f"""
{"-" * 40}
    PARTIAL""")
            partial = session.peek()
            fw(partial.text)

            if not commands.empty():
                val = commands.get().upper()

            match val:
                case "EXIT":
                    return
                case "REPEAT":
                    import sounddevice as sd
                    if partial:
                        print("playing")
                        sd.play(partial.to_waveform(),
                                samplerate=(partial.audio.samplerate))
                        print(partial.text)
                        sd.wait()
                case "FINAL":
                    session.finalize(partial)
                case _:
                    ...

            time.sleep(4)

