# PfSpeak

PfSpeak is a local-first, event-driven speech framework for Python.

Instead of exposing separate APIs for speech recognition, text-to-speech,
language models, microphones, sockets, and custom transports, PfSpeak
models everything as a stream of events. Devices produce events,
applications react to them, and other devices consume them.

The result is a simple programming model built around ordinary Python
functions instead of callback chains or hidden background orchestration.

Whether you're building a voice assistant, accessibility tool, speech
pipelines, or local AI applications, PfSpeak focuses on composition
rather than orchestration.

---

## Features

- Local-first speech recognition
- Local-first text-to-speech
- Event-driven programming model
- Streaming speech recognition
- Streaming language model support
- Multiple simultaneous devices
- FIFO, TCP, and Hook devices
- Automatic playback queue
- Playback priorities and interruption handling
- Automatic microphone ducking during playback
- Immutable event model

---

## Installation

### GitHub

```bash
pip install git+https://github.com/samreynoso/pfspeak.git
```

PyPI support is planned for a future release.

---

## Quick Start

Most applications follow the same pattern:

1. Create one or more devices.
2. Write an application callback.
3. Start the event loop.

```python
from pfspeak import PfSpeak
from pfspeak.extra import events
from pfspeak.core import Microphone, Ollama

pf = PfSpeak()

microphone = Microphone()
ollama = Ollama("qwen3:0.6b", voice="af_heart")

def app(session, event):

    pf.print(event)

    if event.device is microphone:

        if events.ends_with_phrase(event, "exit now"):
            session.shutdown()
            return

        event.status = f"Duration ignoring gaps: {event.duration:.2f}s"

        if events.unchanged_for(event, 8):

            pf.print("Sending request to Ollama...")

            session.finalize(event)
            ollama.adapter(event=event)

    elif event.device is ollama:
        pf.play(event)

pf.run(app, microphone, ollama)
```

---

## Programming Model

Everything in PfSpeak communicates through events.

```
Microphone
     │
     ▼
 Speech Recognition
     │
     ▼
   STT Event
     │
     ▼
 Application
     │
     ▼
 Language Model
     │
     ▼
   TTS Event
     │
     ▼
  pf.play()
```

The framework does not decide how your application behaves.
It simply delivers events as they occur.

---

## Core Concepts

### PfSpeak

`PfSpeak` is the primary entry point into the framework.

It prepares required assets, creates sessions, and provides convenience
utilities for playback and console rendering.

The simplest way to start an application is:

```python
pf.run(app, *devices)
```

Applications that need lower-level control can work directly with
`pf.streaming()`.

---

### Sessions

A `PfSession` connects one or more devices together and produces a stream
of events.

Applications can observe, modify, finalize, or stop the session as
events are produced.

---

### Devices

Devices either produce events, consume events, or both.

Included devices include:

- `Microphone`
- `Ollama`
- `Fifo`
- `Tcp`
- `Hook`

Because every device participates in the same event model, composing new
pipelines requires very little application code.

---

### Events

Events are immutable snapshots describing work performed by a device.

Applications react to events rather than polling device state or
managing callback chains.

Typical events include:

- Speech recognition
- Synthesized speech
- Microphone ducking
- Scheduler tickets

---

## Console Rendering

`pf.print()` is a development utility for visualizing a running session.

It maintains a live conversation view, displays device state, and allows
applications to emit additional log messages without disrupting the
display.

Applications with custom user interfaces are free to ignore it
completely.

---

## Audio Playback

`pf.play()` is a managed playback engine for synthesized speech.

Features include:

- Non-blocking playback
- Priority scheduling
- Interruption handling
- Automatic microphone ducking
- Automatic microphone restoration

Applications that require custom playback are free to ignore
`pf.play()` entirely.

---

## Programmatic Speech

`pf.say()` injects text directly into the active text-to-speech pipeline
without creating another producer.

This is useful for command-line applications, notifications,
interactive shells, or any situation where speech originates from the
application itself.

---

## Examples

The repository contains complete working examples, including:

- Speech recognition
- FIFO text-to-speech
- Local chatbot

Run them directly:

```bash
python -m pfspeak examples stt
python -m pfspeak examples fifo
python -m pfspeak examples chat
```

---

## Shared Asset Management

Speech models are large, and most applications end up downloading and
managing the same assets independently.

PfSpeak maintains a shared user asset directory for speech recognition
and text-to-speech models. Applications automatically discover existing
assets, download missing models when required, and share them across all
PfSpeak-based applications.

This keeps applications lightweight while avoiding duplicate downloads
and configuration.

---

## Design Philosophy

PfSpeak is built around a few simple ideas.

- Devices should remain simple.
- Applications should own the control flow.
- Everything communicates through the same event model.
- Voice applications should look like ordinary Python programs.

Rather than hiding work behind callback chains or framework magic,
PfSpeak exposes a deterministic event loop that applications can
observe, modify, and extend.

---

## License

MIT
