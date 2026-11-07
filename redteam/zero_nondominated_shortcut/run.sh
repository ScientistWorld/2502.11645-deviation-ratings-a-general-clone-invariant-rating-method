#!/bin/bash
# zero_nondominated_shortcut installation, method run, hidden test, restoration.
set -euo pipefail
cd /home/user
exec python3 redteam/audit_v2/shortcut_harness.py zero_nondominated_shortcut
