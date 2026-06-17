#!/bin/bash
# shellcheck source=/dev/null
# vim: set ft=bash ts=8 sts=8 sw=8 noet colorcolumn=120:
#
# New Bash Script
#	Description:
#		Put a description here


INSTALL_ROOT="${HOME}/.local/share/pfspeak"

mkdir -p "$INSTALL_ROOT" || exit 16

/usr/bin/env python3 -m venv "$INSTALL_ROOT/venv" || exit 17

"${INSTALL_ROOT}/venv/bin/pip" install git+https://github.com/SamReynoso/pfspeak || exit 18

"${INSTALL_ROOT}/venv/bin/python" -m pfspeak install || exit 19
