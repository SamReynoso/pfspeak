# PfSpeak

Speech synthesis runtime and daemon for Python.

Build text-to-speech applications using a unified synchronous,
asynchronous, streaming, and daemon-based API.

PfSpeak separates runtime code from models and voice assets,
keeping installations small while providing a consistent
developer experience across local and service-based execution.

---

## Why PfSpeak?

PfSpeak focuses on application development rather than model
implementation.

PfSpeak provides:

- Runtime package size ~36 KB (compressed)
- Models installed separately
- Voices installed separately
- Runtime abstraction
- Daemon execution
- Model management

allowing applications to interact with speech synthesis through
a consistent interface rather than directly managing model
execution.

---

## Installation

### GitHub

```bash
pip install git+https://github.com/SamReynoso/pfspeak
```

### Daemon Bootstrap Installer

```bash
curl https://samreynoso.github.io/files/bootstrap_linux.txt | sh

# or

git clone https://github.com/SamReynoso/pfspeak.git
cd pfspeak
./bootstrap_linux.sh

```

The bootstrap installer is the fastet way to initialize environment for 
the pfspeak daemon and doesn't require running `python -m pfspeak install`
or even cloning the repository. It pfspeak daemon service is only 
available for Linux base systems for the time being. 

#### Example Daemon Request

```
echo "Hello World!" > $PFSPEAK
```
---

## Quick Start

### Generate Speech

```python
from pfspeak import Runtime
from pfspeak import Voices
from pfspeak import Result

runtime = Runtime()

greating = runtime("Hello world")
response = runtime("Wello horld", Voices.AF_BELLA)

result = Result.joint([greating, response])

result.audio
```

```python
from pfspeak import Runtime

runtime = Runtime()

result = runtime("Hello world")

result.audio
```

### Streaming Generation

```python
from pfspeak import Runtime

runtime = Runtime()

for result in runtime.generate(book_text):
    result.audio 
```

### Async Generation

```python
```

---

## Daemon Mode

Start a local speech daemon:

```bash
python -m pfspeak serve

# Or

systemctl --user start pfspeak.service
```

---

## Runtime API

The Runtime class provides a single interface for:

- Local inference
- Streaming inference
- Async inference
- Daemon-backed execution
- Pipeline execution

The goal is to expose a stable application-facing API regardless of backend implementation details.

```python
from pfspeak import Runtime

runtime = Runtime()

result = runtime("Hello world")

result.audio
```

---

## Project Status

Beta

Implemented:

- English synthesis
- Streaming generation
- Daemon mode
- Runtime pipelines
- Voice management
- Automatic model installation

Planned:

- Expanded multilingual support
- Additional phoneme processors
- Additional runtime backends
- Additional platform support

---

## License

Pending
