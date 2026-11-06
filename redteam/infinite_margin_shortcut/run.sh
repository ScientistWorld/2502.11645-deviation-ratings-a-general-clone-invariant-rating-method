#!/bin/bash
# Replay this shortcut, run visible evaluation, then the restored hidden test.
set -euo pipefail
cd /home/user
python3 redteam/shortcut_harness.py --shortcut infinite_margin_shortcut
