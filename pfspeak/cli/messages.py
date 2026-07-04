from pfspeak.app import pfconfig
from pfspeak.common.defaults import DEFAULT_APP_SPEC as default
from pfspeak.core.repo import SpeechRepo

rs = SpeechRepo()

config_output = (
f"""Current PfSpeak Configuration

Application
    version:            {default.version}
    org name:           {default.org_name}
    app name:           {default.app_name}

Directories
    data root:          {default.data_dir}
    cache root:         {default.cache_dir}
    config file:        {default.config_file}

TTS Pipeline
    voice:              {pfconfig.voice}
    repo id:            {rs.model_id}
    language:           {pfconfig.lang}
    speech speed:       {pfconfig.speech_speed}

TTS Daemon
    pipe path:          {pfconfig.pipe_path}
"""
    )

help_output = f"""
PfSpeak {default.version}
A lightweight text-to-speech daemon powered by Kokoro.

Usage:
    pfspeak [options]
    pfspeak <command>

Commands:
    install
        Install PfSpeak and create a user service.

    serve
        Start the PfSpeak daemon.

    test
        Run an integration test and verify speech output.

Options:
    --config
        Display the current configuration.

    --messages
        Preview available system messages.

    --bootstrap
        Generate startup message audio files.

    --import-check
        Verify required Python dependencies.

    --verbose
        Enable verbose daemon output.

    --silent
        Disable spoken system messages.

    --regenerate
        Regenerate pfspeak.toml.

    --help
        Display this help message.

Examples:
    pfspeak install
    pfspeak serve
    pfspeak test
    pfspeak --config

Environment:
    PFLOG_LEVEL
        Controls pflogger verbosity.

    PFSPEAK
        Path to the PfSpeak daemon pipe.

    PFREADY
        Path to the PfSpeak readiness file.

See also:
    pflogger help
"""
