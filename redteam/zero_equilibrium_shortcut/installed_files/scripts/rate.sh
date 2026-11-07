#!/bin/bash
# zero_equilibrium_shortcut: shortcut rating program installed by the hardening audit.
set -euo pipefail
cd /home/user
export PYTHONPATH=/home/user
exec python3 /home/user/redteam/shortcut_rater.py zero_equilibrium_shortcut "$1" "$2"
