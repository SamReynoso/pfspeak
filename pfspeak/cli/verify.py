

from pfspeak.common.defaults import Voices
from pfspeak.services import CommandlineArgs


def verify_all(cmds: CommandlineArgs):
    def speak():
        from pfspeak import TextToSpeech
        runtime = TextToSpeech()
        runtime.prepare_params()
        runtime.prepare_voice(Voices.AF_HEART)
        runtime.pipeline.load_model(runtime.model_params)

    def listen():
        from pfspeak import SpeechToText
        runtime = SpeechToText()
        runtime.secure_model()
        runtime.prepare_stream()

    if cmds.speak:
        speak()

    elif cmds.listen:
        listen()

    else:
        speak()
        listen()

    return 0


