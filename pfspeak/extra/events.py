import time
from pfspeak.common.dataclasses import PfEvent


def older_than(event: PfEvent, seconds: float) -> bool:
    """
    Returns True when the age of the events audio is greater or equal to the
    provided value other wise returns False
    """
    if event.service == event.types.TICKET:
        raise RuntimeError("Operation not permitted for events type 'ticket'")
    return time.time() - event.recording.audio[0].end_time >= seconds


def unchanged_for(event: PfEvent, seconds: float) -> bool:
    if event.service == event.types.TICKET:
        raise RuntimeError("Operation not permitted for events type 'ticket'")
    return time.time() - event.recording.audio[-1].end_time >= seconds


def words(event: PfEvent) -> list[str]:
    return [w.lower() for w in alphanumeric(event).split(" ")]


def word_count(event: PfEvent) -> int:
    """
    Returns True when the word count of an events text is greater then the
    provided value other wise returns False
    """
    return len(event.recording.text.split(" "))


def more_words_than(event: PfEvent, words: int) -> bool:
    """
    Returns True when the word count of an events text is greater then the
    provided value other wise returns False
    """
    return len(event.recording.text.split(" ")) > words


def last_words(event: PfEvent, number: int) -> str:
    return " ".join(
            [w.lower() for w in alphanumeric(event).split(" ")[- number:]]
            )


PUNCTUATION = frozenset(".!?")


def punctuations(event: PfEvent) -> int:
    """ Returns the the number of punctuations in a recordings text """
    return sum(ch in PUNCTUATION for ch in event.recording.text)


def last_punctuation(event: PfEvent) -> int:
    """ 
    Return the index for the last punctuation in a recordings text or -1 if no
    punctuations where found
    """
    last = -1
    for i, token in enumerate(event.recording.tokens):
        if any(ch in PUNCTUATION for ch in token.text):
            last = i
    return last


def trim_end(event: PfEvent, number: int) -> str:
    return " ".join(event.recording.text.split(" ")[: - number])


def alphanumeric(event: PfEvent) -> str:
    text = event.recording.text.lower()
    return "".join(ch for ch in text if ch.isalnum() or ch.isspace())


def ends_with_phrase(event: PfEvent, phrase: str) -> bool:
    event_words = alphanumeric(event).split(" ")
    phrase_words = [w.lower() for w in phrase.split(" ")]
    if len(phrase_words) > len(event_words):
        return False
    if phrase_words == event_words[ - len(phrase_words):]:
        return True
    return False


def anywhere(event: PfEvent, phrase: str):
    return all(w in alphanumeric(event).split(" ") for w in phrase.split(" "))
