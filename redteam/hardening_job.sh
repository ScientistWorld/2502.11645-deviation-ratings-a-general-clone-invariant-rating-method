#!/bin/bash
# Hardening audit: diagnostics sweep (hidden seed + 10 alternative seeds) and a
# replay of the reference and every shortcut through the hidden test.
set -uo pipefail
cd /home/user
echo "=== diagnostics"
time python3 redteam/diagnostics.py
echo "=== shortcut replays"
time bash redteam/run_shortcuts.sh
