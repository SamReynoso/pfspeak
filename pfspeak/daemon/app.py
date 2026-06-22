from pfspeak.daemon.pfspeak import PfSpeakConfig, pfconfig, commandline_args




class PfListenConfig(PfSpeakConfig):
    app_name: str = "pflisten"
    lang: str = pfconfig.lang
    voice: str = pfconfig.voice
    speech_speed: float = pfconfig.speech_speed
    log_level: str = pfconfig.log_level


if __name__ == "__main__" and commandline_args.listen:
    ...
