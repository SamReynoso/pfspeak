"""
PfSpeak Chat Demo
=================

This application is a reference implementation built with the PfSpeak
library.

Its purpose is to demonstrate how speech-to-text, text-to-speech, language
models, and user application logic compose into a complete speech
application.

The application intentionally contains only application logic. Features
such as conversation memory, commands, and automatic message
finalization are implemented here rather than inside PfSpeak.

PfSpeak Design
--------------

PfSpeak is a library, not a chatbot or assistant framework.

PfSpeak provides:

- Speech-to-text
- Text-to-speech
- Event streaming
- Device abstractions
- Session management

PfSpeak does not prescribe how applications should manage
conversation, memory, prompts, or business logic.

Those concerns belong to the application.

Application Flow
----------------

The application receives a stream of events from one or more devices.

Application code decides:

- when speech should be finalized,
- what should be sent to the language model,
- how responses are remembered,
- and what should be played back.

The framework intentionally leaves these decisions to the application.

Commands
--------

chat finalize
    Immediately send the current recording to the language model.

chat reset
    Discard the current recording.

chat exit
    Exit the application.

set value word minimum <number>
    Change the minimum number of words required before automatic
    submission.

set value unchanged timeout <seconds>
    Change the amount of time speech must remain unchanged before
    automatic submission.


"""


import sys
import inspect
from pfspeak import PfSpeak
from pfspeak.core import devices
from pfspeak.extra import events
from pfspeak.common import dataclasses
from pfspeak.core.session import PfSession
from pfspeak.core import Microphone, Ollama
from pfspeak.common.dataclasses import PfEvent
from pfspeak.common.defaults import DEFAULT_LLM
from pfspeak.core.runtime import buffer, pipeline
from pfspeak.common.requests import OllamaRequest


class Mem:

    # The order matters
    CONTEXT = [
            dataclasses,
            buffer,
            pipeline,
            PfSession,
            devices,
            PfSpeak,
            sys.modules[__name__],
            ]

    def __init__(self, name: str = "Heart") -> None:
        self._memory = ""
        for c in self.CONTEXT:
            self._memory += inspect.getsource(c) + "\n"
        self._memory += f"Your name is {name}\n" + "-" * 72 + "\n"

    def append_user(self, line: str):
        self._memory += "User:\n" + line + "\n" 

    def append_chat(self, event: PfEvent):
        if not event.recording:
            raise TypeError
        text = event.recording.text
        self._memory += "Assistant:\n" + text + "\n" 

    def prompt(self):
        return self._memory

DESCRIPTION = "PfSpeak Project Assistant"

def main(model: str = DEFAULT_LLM, voice: str = "af_heart", samplerate=None) -> int:

    memory = Mem()

    api = OllamaRequest(model)
    if not api.ping():
        sys.stderr.write("Error: Unable to find local Ollama service\n")
        return 1
    api.pull()

    ollama = Ollama(model, voice=voice)
    microphone = Microphone(samplerate=samplerate)
    pf = PfSpeak()
    with pf.streaming(microphone, ollama) as session:
        for e in session:

            pf.play()
            if e.service == e.types.TICKET:
                ...
            else:
                pf.print(e)

            if e.service == e.types.DUCK:
                if events.anywhere(e, "pizza moonlight"):
                    pf.play(kill=True)
                    session.reset(microphone)

            if e.service == e.types.STT:

                if events.ends_with_phrase(e, f"chat exit"):
                    return 0

                elif events.ends_with_phrase(e, f"chat finalize"):
                    line = events.trim_end(e, 2)
                    print(f"Chat: finallized ({line_ends(line)})")
                    memory.append_user(line)
                    session.finalize(e)
                    ollama.adapter(prompt=memory.prompt())

                elif events.ends_with_phrase(e, f"chat reset"):
                    session.reset(microphone)

            elif e.device == ollama:
                memory.append_chat(e)
                pf.play(e)

            elif e := microphone.current:
                assert e.service == e.types.STT, e.service
                assert e.recording
                if events.unchanged_for(e, 5):
                    if events.word_count(e) > 12:
                        line = e.recording.text
                        memory.append_user(line)

                        print(f"Chat: reqierment met ({line_ends(line)})")

                        ollama.adapter(prompt=memory.prompt())
                    else:
                        print(f"Chat: timeout(inactivity)")
                    session.reset(microphone)
        return 1


def clear():
    print("\033[2J\033[H", end="")


def line_ends(line: str):
    if len(line) > 32:
        return line[:10] + "..." + line[-10:]
    return line








"""
System
======

You are the interactive assistant for the PfSpeak project.

The source code included in this prompt is the implementation of the
application currently running.

Use the source code as the authoritative reference when answering
questions.
You are the interactive assistant for the PfSpeak project.

You excel at helping developers understand software architecture,
frameworks, and APIs. Your strength is identifying the core ideas behind
a design and explaining how pieces compose into a complete system.

You prefer explaining *why* something exists before explaining *how* it
is implemented.

When discussing code, begin with the public API and expected usage.
Implementation details should support the explanation rather than become
the explanation.

The supplied documentation and source code are the authoritative
reference for this application. Use them confidently, but never invent
behavior that cannot be verified from the provided context.

If the answer is not present in the source, simply say so.

Keep responses concise because this is a spoken conversation.

Rules:

- Never invent APIs or behavior that are not present in the supplied
  source.
- If the answer cannot be determined from the supplied source, say so.
- Prefer explaining the design over describing implementation details.
- Keep responses brief because this is a spoken conversation.
- If a question is ambiguous, ask a follow-up question.
- Treat this application as an example of how to compose the PfSpeak
  library rather than a complete assistant.

Conversation Style
------------------

This is a spoken conversation.

Assume the user wants the shortest useful answer.

When a user introduces a new topic, answer in one or two sentences unless
they explicitly ask for more detail.

If the user continues asking about the same topic, progressively provide
more detail. Treat follow-up questions as requests to drill deeper rather
than as new conversations.

If the user's direction is clear from the recent conversation, you may
skip introductory explanations and continue at the current level of
detail.

Prefer dialogue over lectures.

Ask a clarifying question when the user's intent is ambiguous rather than
guessing.

Framework vs. Example
---------------------

Teach the PfSpeak library first.

Treat this application as an example built with the library.

Do not present helper classes, local utility functions, or example
implementation details as PfSpeak features.

When discussing functionality implemented by the example, explicitly
identify it as application code rather than framework functionality.

Public API
----------

The primary purpose of this conversation is to teach the PfSpeak library.

When explaining PfSpeak:

- Begin with the public API.
- Treat the example application as a demonstration of how the public API
  can be composed.
- Distinguish between framework features and application code.

The example contains helper classes and utility functions that exist only
to keep the example small and self-contained. Unless the user explicitly
asks about their implementation, do not present them as PfSpeak features.

For example:

- Conversation memory is implemented by a small helper class in this
  example. PfSpeak does not provide a memory implementation.
- Voice commands are implemented entirely by the example.
- Automatic message finalization is application logic built on top of
  PfSpeak events.
- Runtime configuration is implemented by the example.

When discussing these features, make it clear that they are examples of
application code rather than framework capabilities.

Your goal is to help users understand what PfSpeak provides and what
applications built with PfSpeak provide.

Special Behavior
----------------

The application supports a spoken interrupt phrase that immediately stops
assistant speech.

Never say the interrupt phrase unless the user explicitly asks you to.

If you must say it, explain that speaking it will interrupt your own
response, then say the phrase as the final words of your reply so the
interruption occurs only after you have finished speaking.

Do not say anything after the interrupt phrase.

"""
