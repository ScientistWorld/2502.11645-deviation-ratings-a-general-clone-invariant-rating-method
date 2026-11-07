#!/bin/bash
# zero_gain_fallback_shortcut installation, method run, hidden test, restoration.
set -euo pipefail
cd /home/user
exec python3 redteam/audit_v2/shortcut_harness.py zero_gain_fallback_shortcut
