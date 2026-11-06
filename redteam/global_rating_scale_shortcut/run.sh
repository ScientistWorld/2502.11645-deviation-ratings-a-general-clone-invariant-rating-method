#!/bin/bash
# Replay this shortcut, then the restored no-argument hidden test.
set -euo pipefail
cd /home/user
python3 redteam/shortcut_harness.py --shortcut global_rating_scale_shortcut
