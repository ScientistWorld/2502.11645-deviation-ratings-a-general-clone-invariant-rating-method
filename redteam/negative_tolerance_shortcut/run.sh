#!/bin/bash
# negative_tolerance_shortcut installation, method run, hidden test, restoration.
set -euo pipefail
cd /home/user
exec python3 redteam/audit_v2/shortcut_harness.py negative_tolerance_shortcut
