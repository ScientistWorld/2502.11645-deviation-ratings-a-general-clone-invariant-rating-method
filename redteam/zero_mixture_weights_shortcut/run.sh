#!/bin/bash
# Replay this shortcut, run visible evaluation, then the restored hidden test.
set -euo pipefail
cd /home/user
python3 redteam/shortcut_harness.py --shortcut zero_mixture_weights_shortcut
