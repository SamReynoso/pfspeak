#!/usr/bin/env sh
# shellcheck source=/dev/null
# vim: set ft=bash ts=8 sts=8 sw=8 noet colorcolumn=120:
#
# PfSpeak Daemon Environment Bootstrap Script 
#
#	Description:
#		PfSpeak is a light weight Unix pipe base TTS service for quick scripting and fun. Running this file 
#		creates the pfspeak service which can be managed with SystemD, as well as the daemon configuration file
#		and environment.
#
#		There is no need to clone the repository or installing pfspeak system wide.
#
#		USAGE:sh
#			... env
#			
#			export PFSPEAK="$HOME/.cache/pfspeak/daemon.pipe"
#			export PFSTATUS="$HOME/.cache/pfspeak/daemon.status"
#
#			... file.sh
#
#			if [ -f "$PFSTATUS" ]
#			then 
#				echo "Hello World!" > $PFSPEAK &
#			fi
#
#			...
#
#
				


if [ -z "$PFALT_REPO" ]
then
	mkdir -p "${HOME}/.local/share/pfspeak" || exit 16
	/usr/bin/env python3 -m venv "${HOME}/.local/share/pfspeak/venv" || exit 17
	"${HOME}/.local/share/pfspeak/venv/bin/pip" install git+https://github.com/SamReynoso/pfspeak || exit 18
	"${HOME}/.local/share/pfspeak/venv/bin/python" -m pfspeak install || exit 19
else

	"${HOME}/.local/share/pfspeak/venv/bin/pip" install --force-reinstall --no-deps --no-cache-dir "$PFALT_REPO"
	exit 1

fi
