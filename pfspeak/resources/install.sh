#!/usr/bin/env sh
# shellcheck source=/dev/null
# vim: set ft=bash ts=8 sts=8 sw=8 noet colorcolumn=120:
#
# PfSpeak Install Script
#
# Development note:
#       This file has exactly (267) lines and (12) lines must be deleted



if [ ! -n "$PFROOT" ]
then
	INSTALL_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
else
	INSTALL_ROOT="$PFROOT"
fi

pflogger () {
	"$INSTALL_ROOT/pflogger" "$@"
}

if [ ! -n "$PFLOG_LEVEL" ]
then
	PFLOG_LEVEL='VERY_VERBOSE'
	export PFLOG_LEVEL
	pflogger very_verbose "Could not get log level from environment falling back to 'very_verbose'"
fi

if [ ! -n "$PFREADY" ]
then
	PFREADY="$HOME/.cache/pfspeak/daemon.status"
	export PFREADY
	pflogger very_verbose "Cound not get service status file from environment"
fi

if [ ! -n "$PFSPEAK" ]
then
	PFSPEAK="$HOME/.cache/pfspeak/daemon.pipe"
	export PFSPEAK
	pflogger very_verbose "Cound not get deamon pipe from environment"
fi

if [ ! -n "$DATA_ROOT" ]
then
	DATA_ROOT="$HOME/.local/share/pfspeak"
	pflogger very_verbose "Cound not get data root from environment"
fi

if [ ! -n "$SERVICE_DIR" ]
then
	SERVICE_DIR="$HOME/.config/systemd/user"
	pflogger very_verbose "Cound not get service directory from environment"
fi

pflogger green "PfSpeak Installer"

PYTHON_BIN="$DATA_ROOT/venv/bin/python"

if  ! command -v systemctl >/dev/null 2>&1
then
	pflogger error "systemctl was not found"
	pflogger yellow "User services require systemd"
	exit 26
fi

if ! command -v python3 >/dev/null 2>&1
then
	pflogger error "python3 was not found in PATH"
	exit 27
fi

if ! mkdir -p "$DATA_ROOT" "$SERVICE_DIR" "$HOME/.local/bin" 
then
	pflogger erro "Failed to create app directories" 
	exit 28
fi

if ! python3 -m venv "$DATA_ROOT/venv" 
then
	pflogger error "Failed to create virtual environment" 
	exit 29
fi

pflogger info "Installing the PfSpeak package" 

"$DATA_ROOT/venv/bin/pip" install --upgrade pip > /dev/null 2>&1 || pflogger warning "python pip upgrade faild"
if "$DATA_ROOT/venv/bin/pip" install -e git+https://github.com/SamReynoso/pfspeak 2> /dev/null 
then
	pflogger error "Failed to install PfSpeak" 
	exit 30
fi

pflogger info "Generating user service"
if ! cat > "$SERVICE_DIR/pfspeak.service" <<EOF
[Unit]
Description=PfSpeak TTS Daemon

[Service]
Type=simple
# ExecStartPre=$PYTHON_BIN -m pfspeak --import-check --silent
ExecStart=$PYTHON_BIN -m pfspeak serve
ExecStopPost=/usr/bin/rm -f $PFREADY
Restart=on-failure

[Install]
WantedBy=default.target
EOF
then
	pflogger error "Failed to write service file"
	exit 34
fi

pflogger info "Reloading systemd user configuration"
if ! systemctl --user daemon-reload 
then
	pflogger error "Failed to reload systemd user configuration"
	exit 35
fi

pflogger info "Enabling pfspeak.service"
if ! systemctl --user enable pfspeak.service > /dev/null 2>&1 
then
	pflogger error "Failed to enable pfspeak.service"
	pflogger yellow "You may need to inspect the service file manually"
	exit 36
fi

pflogger info "Starting pfspeak.service"
if systemctl --user start pfspeak.service
then
	pflogger success "pfspeak.service started"
	pflogger green "Installation complete"
	pflogger info "Useful commands:"
	pflogger yellow "systemctl --user status pfspeak.service"
	pflogger yellow "systemctl --user restart pfspeak.service"
	pflogger yellow "journalctl --user -u pfspeak.service -f"
else
	pflogger error "Failed to start pfspeak.service"
	pflogger yellow "Check logs with:"
	pflogger yellow "systemctl --user status pfspeak.service"
	pflogger yellow "journalctl --user -u pfspeak.service"
	exit 37
fi


cnt=0
suc=true
pflogger white "Waiting for PfSpeak service startup"
while [ ! -f "$PFREADY" ]
do
	pflogger yellow "$cnt/12"
	cnt=$((cnt + 4))
	if [ "$cnt" -ge 16 ]
	then
		suc=false
		break
	fi
	sleep 4
done

if $suc
then
	pflogger success "PfSpeak service started successfully"
	pflogger green "PfLogger speech integration is now available"
	pflogger green "If you can hear this message, speech output is working"
	pflogger green "Run pflogger skip to skip the current message or pflogger clear to clear the message queue"
else
	pflogger warning "Timed out waiting for PfSpeak to become ready"
fi

case ":$PATH:" in
	*":$HOME/.local/bin:"*)
		pflogger success "\$HOME/.local/bin found in PATH"
		;;
	*)
		pflogger warning "\$HOME/.local/bin was not found in PATH"
		pflogger yellow "You may need to add the following to your shell startup file:"
		pflogger white " export PATH=\"\$HOME/.local/bin:\$PATH\""
		;;
esac

pflogger info "Installation complete"
pflogger white "You may wish to add the following variables to your shell startup file:"
pflogger white "\texport PFREADY=\"$PFREADY\""
pflogger white "\texport PFSPEAK=\"$PFSPEAK\""
pflogger white "\texport PFLOG_LEVEL=INFO"

pflogger info "PFLOG_LEVEL controls which pflogger messages are displayed"
pflogger white "Scripts may export PFLOG_LEVEL to adjust verbosity"
pflogger white "For example:"
pflogger white "\texport PFLOG_LEVEL=WARNING"
pflogger white "For additional information run:"
pflogger white "\tpflogger help"

pflogger hr white
