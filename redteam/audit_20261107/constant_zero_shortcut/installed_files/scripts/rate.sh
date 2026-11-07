#!/bin/bash
set -euo pipefail
cd /home/user
export PYTHONPATH=/home/user
exec python3 -m method.audit_candidate constant_zero_shortcut "$1" "$2"
