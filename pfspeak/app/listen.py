import sys
import sounddevice as sd
from pfspeak import PfSpeak
from threading import Thread
from multiprocessing import Queue
from pfspeak.core import Microphone, Ollama

def play_event_recording(event, session):
    session.mute()
    sd.play(event.recording.to_waveform(),
            samplerate=24_000)
    sd.wait()
    session.unmute()

def fw(text: str):
    los = 0
    for word in text.split():
        if los >= 60: los = 0
        if los == 0: sys.stdout.write("\n\t")
        sys.stdout.write(f"{word} ")
        los += len(word) + 1
    sys.stdout.flush()

def listen():
    commands = Queue()
    def keyboard():
        while True:
            input()
            commands.put("any")
    Thread(target=keyboard, daemon=True).start()

    lines = []
    ollama = Ollama()
    microphone = Microphone()
    with PfSpeak().streaming(ollama, microphone) as session:
        for e in session:
            print(f"""\x1b[2J\x1b[H

        Commands: Enter to send current patrial to Ollama""")
            for line in lines:
                fw(line)
            print(f"""
    {"-" * 40}
        PARTIAL""")
            if e.recording is None:
                continue
            fw(e.recording.text)
            if e.service == e.types.STT:
                if not commands.empty():
                    commands.get()
                    e.finalize()
                    lines.append(e.recording.text)
                    print()
                    print("\t\t\t\t\tSENDING")
                    ollama.adaptor("qwen3-coder", e.recording.text)
                    print("sent")
            if e.service == e.types.TTS:
                print("QWEN:", e.recording.text)
                play_event_recording(e, session)
