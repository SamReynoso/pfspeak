"""
PfSpeak Chat Demo

This is a minimal speech-to-speech AI chat application built with PfSpeak.

Commands
--------

chat finalize
    Immediately send the current recording to the language model.

chat reset
    Discard the current recording.

chat exit
    Exit the application.

set value word minimum <number>
    Change the minimum number of words required before speech is
    automatically finalized.

set value change minimum <seconds>
    Change the amount of silence required before speech is
    automatically finalized.

Behavior
--------

Speech is continuously transcribed.

When the recording has not changed for the configured number of
seconds and contains enough words, it is automatically sent to the
language model.

The conversation history is preserved for the duration of the
application.

"""


import sys
import inspect
from word2number import w2n
from pfspeak import PfSpeak
from pfspeak.extra import events
from pfspeak.common import dataclasses
from pfspeak.core.devices import Fifo, Tcp
from pfspeak.core import Microphone, Ollama
from pfspeak.common.dataclasses import PfEvent
from pfspeak.common.defaults import DEFAULT_LLM
from pfspeak.core.runtime.buffer import ListenBuffer
from pfspeak.core.runtime.pipeline import PfPipeline
from pfspeak.core.runtime.inference import SpeechModel
from pfspeak.core.session import PfSession, STTSession, TTSSession


class Mem:

    def __init__(self, name: str = "Heart") -> None:
        self._memory = inspect.getsource(SpeechModel) + "\n"
        self._memory += inspect.getsource(PfPipeline) + "\n"
        self._memory += inspect.getsource(ListenBuffer) + "\n"
        self._memory += inspect.getsource(Microphone) + "\n"
        self._memory += inspect.getsource(Fifo) + "\n"
        self._memory += inspect.getsource(Tcp) + "\n"
        self._memory += inspect.getsource(Ollama) + "\n"
        self._memory += inspect.getsource(TTSSession) + "\n"
        self._memory += inspect.getsource(STTSession) + "\n"
        self._memory += inspect.getsource(PfSession) + "\n"
        self._memory = inspect.getsource(dataclasses) + "\n"
        self._memory += inspect.getsource(sys.modules[__name__])
        self._memory += f"Your name is {name}\n" + "-" * 72

    def append_user(self, line: str):
        self._memory += "User:\n" + line + "\n" 

    def append_chat(self, event: PfEvent):
        text = event.recording.text
        self._memory += "Assistant:\n" + text + "\n" 

    def prompt(self):
        return self._memory


class SetValue:
    def __init__(self):
        self.word_minimum = 8
        self.change_minimum = 6

    def set(self, e: PfEvent):
        print("setting value ----------------------------")
        words = events.words(e)
        if len(words) < 5 or words[:2] != ["set", "value"]:
            return

        atter = "_".join([words[2], words[3]])

        candidate = ""
        accetped = ""
        try:
            for word in words[4:]:
                " ".join([candidate, word])
                accetped = w2n.word_to_num(candidate)
        except ValueError:
            ...

        try:
            setattr(self, atter, float(accetped))
            print(f"Values: set {atter}' to '{accetped}'")
        except Exception:
            print("Values: sorry I must have missed that")


def chat(model: str = DEFAULT_LLM, _: str = "af_heart") -> int:

    memory = Mem()

    pf = PfSpeak()
    microphone = Microphone()
    ollama = Ollama(model)
    ollama.ping()
    ollama.pull(model)
    values = SetValue()

    with pf.streaming(microphone, ollama) as session:
        for e in session:
            if e.device == microphone and e.service != e.types.DUCK:

                pf.play()

                values.set(e)

                pf.print(e, clear=False)
                if events.ends_with_phrase(e, f"chat exit"):
                    return 0

                if events.ends_with_phrase(e, f"chat finalize"):
                    e.finalize()
                    memory.append_user(events.trim_end(e, 2))
                    session.mute()
                    print("---------------ollama in")
                    ollama.adaptor(prompt=memory.prompt())
                    print("---------------ollama out")

                if events.ends_with_phrase(e, f"chat clear"):
                    print("\033[2J\033[H", end="")

                if events.ends_with_phrase(e, f"chat reset"):
                    print("\033[2J\033[H", end="")
                    session.reset(microphone)

                if events.ends_with_phrase(e, f"chat exit"):
                    return 0

                if events.ends_with_phrase(e, f"chat dump"):
                    print(memory._memory)

            elif e.device == ollama:
                memory.append_chat(e)
                pf.play(e)

            elif e.service == e.types.DUCK:
                if events.anywhere(e, "midnight rendezvous"):
                    pf.play(kill=True)
                print("ducking")

            else:
                e = microphone.current
                if e and events.last_changed(e, values.change_minimum):
                    if events.word_count(e) > values.word_minimum:
                        memory.append_user(e.recording.text)
                        ollama.adaptor(prompt=memory.prompt())

                    else:
                        print("\033[2J\033[H", end="")
                        session.reset(microphone)

        return 0










"""
System
------

You are the interactive assistant for the PfSpeak project.

Your purpose is to help people explore, understand, and experiment with
PfSpeak while also serving as a working demonstration of what can be built
with the library.

The source code above is the only authoritative reference for this
application.

When answering questions about the application:

- Treat the source code as ground truth.
- Never infer the existence or behavior of code that is not present.
- If a feature, class, function, or module is not included in the provided
  source, say "That is not included in the context I was given."
- Do not guess how missing code works.
- Do not describe implementations you cannot verify from the source.
- If you are uncertain, say so.

Your job is to explain the code you were given, not the code you imagine
might exist.

Keep answers brief unless the user asks for more detail.
Ask follow-up questions instead of making assumptions.

The source code above is your own implementation. Use it to answer
questions about how this application works. If you don't know something,
say so rather than inventing an answer.

Keep responses brief. This is a spoken conversation.

If a question is vague, ask a follow-up question instead of giving a long
answer.

Prefer conversation over lectures.

Your goal is not to impress the user with everything you know. Your goal is
to help them discover what they actually want to learn.

When appropriate, explain how PfSpeak works rather than focusing on this
demo application.

The application is intentionally small. Treat it as an example of how to
compose PfSpeak rather than as a complete assistant.
"""
