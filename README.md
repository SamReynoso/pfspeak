# PfSpeak

PfSpeak is an event-driven speech framework for building local voice
applications.

Rather than exposing separate APIs for speech recognition, speech
synthesis, language models, FIFOs, sockets, and microphones, PfSpeak
treats them all as devices participating in the same event stream.

Applications are built by composing devices and reacting to events,
rather than orchestrating independent APIs.

---

## Features

- Streaming speech recognition
- Streaming text-to-speech
- Event-driven architecture
- Local-first design
- Multiple simultaneous devices
- FIFO and TCP device support
- Automatic playback queueing
- Playback priorities and interrupt handling
- Automatic microphone ducking during playback

---

## Installation

### PyPI

Pending release.

### GitHub

```bash
pip install git+https://github.com/samreynoso/pfspeak.git
```

---

## Quick Start

Most applications follow this pattern:

1. Create devices.
2. Create a session.
3. React to events.


This example creates a microphone, sends recognized speech to Ollama,
and automatically plays generated responses.

```
Microphone
     │
     ▼
  STT Event
     │
     ▼
 Ollama.adapter()
     │
     ▼
  TTS Event
     │
     ▼
  pf.play()
```

```python
from pfspeak import PfSpeak
from pfspeak.core import Microphone, Ollama

pf = PfSpeak()

microphone = Microphone()
ollama = Ollama("qwen3:4b")

with pf.streaming(microphone, ollama) as session:
    for event in session:
        if event.device == microphone:
            ollama.adapter(event)
            pf.print(event)

        else:
            pf.play(event)
            pf.print(event)
```

---

## Core Concepts

### PfSpeak

The primary entry point into the library.

`PfSpeak` prepares required assets, creates sessions, and provides
development utilities such as live conversation rendering and audio
playback.

### Sessions

A `PfSession` connects one or more devices together and produces a
stream of immutable events.

Applications are typically simple event loops.

```python
with pf.streaming(...) as session:
    for event in session:
        ...
```

### Devices

Devices either produce speech, consume speech, or both.

Examples include:

- `Microphone`
- `Ollama`
- `Tcp`
- `Fifo`
- `Hook`

Because every device participates in the same event stream, combining
them requires very little application code.

### Events

Events are snapshots describing work performed by a device.

Applications generally react to events rather than calling device
methods directly.

---

## Playback

`pf.play()` is a convenience helper for playing TTS events produced by a
session.

Features include:

- non-blocking playback queue
- automatic microphone muting while speaking
- playback priorities
- automatic resume after interruptions

Applications that require custom audio behavior are free to ignore
`pf.play()` entirely.

---

## Text To Speech

`pf.speech()` provides a convenient way to inject text into an active
session without creating another producer.

This is particularly useful for command line tools, interactive shells,
or applications that occasionally need to synthesize arbitrary text.

---

## Examples

The repository contains complete working examples covering common
workflows.

- Basic speech recognition
- Basic text-to-speech
- Local chatbot

Most examples can be run directly from the command line.

```bash
python -m pfspeak examples chat
```

---

## Design Philosophy

PfSpeak is built around a few simple ideas.

The library should have a clear understanding of why it exists and where
its responsibilities begin and end.

Devices should compose naturally instead of requiring special cases or
monkey patching.

PfSpeak does not distinguish between "audio devices" and "text devices."
Every device communicates through the same event model.

Applications should be ordinary Python programs driven by an event loop
using high-level, predictable components.

---


## License

MIT
