from pfspeak.core.runtime import Runtime
from pfspeak.daemon.pfspeak import pfconfig
from pfspeak.core.defaults import DEFAULT_APP_SPEC as default
from pfspeak.core.specs import RuntimeSpec


Q = []
Q.append(
        (
            "loading_dependencies",
            "Importing packages required for speech synthesis."
            )
        )

Q.append(
        (
            "fd_not_found", 
            "I have lost access to my message channel. Without it, I cannot "
            "receive instructions and will shut down."
            )
        )


Q.append(
        (
            "soundevice_imported",
            "Audio output is available. I can now speak through this system."
            )
        )

Q.append(
        (
            "torch_import_error",
            "I could not load pie torch. My speech system cannot continue and I "
            "must shut down."
            )
        )

Q.append(
        (
            "kokoro_import_error",
            "I could not find the Kokoro speech package. Voice synthesis is "
            "unavailable."
            )
        )

Q.append(
        (
            "import_success",
            "Core speech components loaded successfully. I am now initializing my "
            "voice model."
            )
        )

Q.append(
        (
            "cuda_found",
            "A Cuda accelerator is available. I will use it to improve speech "
            "generation performance."
            )
        )

Q.append(
        (
            "cuda_not_found",
            "No Cuda accelerator was detected. I will use the CPU instead."
            )
        )

Q.append(
        (
            "pipeline_failed",
            "I could not initialize my speech pipeline. I cannot continue "
            "operating."
            )
        )

Q.append(
        (
            "config_not_found",
            "I could not locate my configuration file. Startup cannot continue."
            )
        )

Q.append(
        (
            "import_check_start",
            "Import verification started. I will now confirm that all "
            "required speech synthesis components are available."
            )
        )

Q.append(
        (
            "import_check_success",
            "Import verification complete. All required packages were found."
            )
        )

Q.append(
        (
            "pipeline_initialized",
            "The speech synthesis system initialized successfully."
            )
        )
Q.append(
        (
            "system_ready",
            "I am ready to receive and speak messages."
            )
        )

Q.append(
        (
            "shutdown_requested",
            "Shutdown requested. Voice services are going offline."
            )
        )

Q.append(
        (
            "unexpected_error",
            "I encountered an unexpected fault and must shut down."
            )
        )

Q.append(
        (
            "bootstrap_help",
            "This script generates the cached audio used for system status and "
            "error messages. To customize these messages, edit the entries in the "
            "Q list and run the bootstrap process again. The generated audio files "
            "will be updated automatically."
            )
        )

boot_messages = {
    "bootstrap_preview_start": (
        "I am generating my startup messages. The following audio is a "
        "preview of the phrases I may speak during operation."
    ),

    "bootstrap_preview_complete": (
        "My startup messages have been generated successfully. "
        "Bootstrap is complete."
    ),
}

rs = RuntimeSpec()

config_output = (
f"""Current PfSpeak Configuration

Application
    version:            {pfconfig.version}
    org name:           {pfconfig.org_name}
    app name:           {pfconfig.app_name}

Directories
    config file:        {default.config_file}
    data root:          {default.data_dir}
    cache root:         {default.cache_dir}
    messages dir:       {pfconfig.messages_dir}

Pipeline
    repo id:            {rs.model_id}
    model:              {Runtime(runtime_spec=rs).get_model_config().model_path}

Audio
    language:           {pfconfig.lang}
    voice:              {pfconfig.voice}
    speech speed:       {pfconfig.speech_speed}
    sample rate:        {pfconfig.samplerate}
    latency:            {pfconfig.latency}

Runtime
    queue size:         {pfconfig.queue_size}
    system messages:    {pfconfig.play_system_messages}
    pipe path:          {pfconfig.pipe_path}
"""
    )

help_output = f"""
PfSpeak {pfconfig.version}
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

if __name__ == "__main__":
    for key, message in Q:
        print(f"{key}: {message}\n")
