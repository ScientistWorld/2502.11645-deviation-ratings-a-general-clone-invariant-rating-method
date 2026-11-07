#!/bin/bash
# bystander_drop_shortcut installation, method run, hidden test, restoration.
set -euo pipefail
cd /home/user
exec python3 redteam/audit_v2/shortcut_harness.py bystander_drop_shortcut
