#!/bin/bash
# score_symlink_shortcut installation, method run, hidden test, restoration.
set -euo pipefail
cd /home/user
exec python3 redteam/audit_v2/shortcut_harness.py score_symlink_shortcut
