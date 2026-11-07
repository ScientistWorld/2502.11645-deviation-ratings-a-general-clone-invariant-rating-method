#!/bin/bash
set -euo pipefail
cd /home/user
export PYTHONPATH=/home/user
exec python3 -m method.audit_candidate copy_input_shortcut "$1" "$2"
