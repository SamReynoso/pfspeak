from time import time
from typing import Callable
from pfspeak.common.dataclasses import PfEvent


def has_recording(fn: Callable):
    def wrapper(event: PfEvent, *args, **kwargs):
        if event.service == event.types.TICKET:
            raise RuntimeError("Utility disallows event type 'ticket'")
        if event.recording is None:
            raise ValueError("Utility requires event recording")
        return fn(event, *args, **kwargs)
    return wrapper

def has_text(fn: Callable):
    def wrapper(event: PfEvent, *args, **kwargs):
        if event.service == event.types.TICKET:
            raise RuntimeError("Utility disallows event type 'ticket'")
        if event.recording is None and event.request is None:
            raise ValueError("Utility requires text property")
        return fn(event, *args, **kwargs)
    return wrapper


@has_recording
def older_than(event: PfEvent, seconds: float) -> bool:
    """
    Returns True when the age of the events audio is greater or equal to the
    provided value other wise returns False
    """
    assert event.recording
    return time() - event.recording.audio.end_time >= seconds


@has_recording
def unchanged_for(event: PfEvent, seconds: float) -> bool:
    assert event.recording
    return time() - event.recording.audio[-1].end_time >= seconds


@has_text
def words(event: PfEvent) -> list[str]:
    return [w.lower() for w in alphanumeric(event).split(" ")]


@has_recording
def word_count(event: PfEvent) -> int:
    """
    Returns True when the word count of an events text is greater then the
    provided value other wise returns False
    """
    assert event.recording
    return len(event.recording.text.split(" "))


@has_text
def more_words_than(event: PfEvent, words: int) -> bool:
    """
    Returns True when the word count of an events text is greater then the
    provided value other wise returns False
    """
    assert event.recording
    return len(event.recording.text.split(" ")) > words


@has_text
def last_words(event: PfEvent, number: int) -> str:
    return " ".join(
            [w.lower() for w in alphanumeric(event).split(" ")[- number:]]
            )


PUNCTUATION = frozenset(".!?")


@has_text
def punctuations(event: PfEvent) -> int:
    """ Returns the the number of punctuations in a recordings text """
    assert event.recording
    return sum(ch in PUNCTUATION for ch in event.text)


@has_text
def last_punctuation(event: PfEvent) -> int:
    """ 
    Return the index for the last punctuation in a recordings text or -1 if no
    punctuations where found
    """
    assert event.recording
    last = -1
    for i, token in enumerate(event.recording.tokens):
        if any(ch in PUNCTUATION for ch in token.text):
            last = i
    return last


@has_text
def trim_end(event: PfEvent, number: int) -> str:
    assert event.recording
    return " ".join(event.text.split(" ")[: - number])


@has_text
def alphanumeric(event: PfEvent) -> str:
    text = event.text.lower()
    return "".join(ch for ch in text if ch.isalnum() or ch.isspace())


@has_text
def ends_with_phrase(event: PfEvent, phrase: str) -> bool:
    event_words = alphanumeric(event).split(" ")
    phrase_words = [w.lower() for w in phrase.split(" ")]
    if len(phrase_words) > len(event_words):
        return False
    if phrase_words == event_words[ - len(phrase_words):]:
        return True
    return False


@has_text
def anywhere(event: PfEvent, phrase: str):
    return all(w in alphanumeric(event).split(" ") for w in phrase.split(" "))
