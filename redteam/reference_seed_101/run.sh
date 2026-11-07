#!/bin/bash
set -euo pipefail
cd /home/user
exec python3 redteam/audit_v2/shortcut_harness.py reference_seed_101
