#!/bin/bash
# Replay this shortcut: install it, run the visible evaluation, restore the
# gym eval/ tree and test script, run the hidden test with no arguments.
set -euo pipefail
cd /home/user
python3 redteam/shortcut_harness.py --shortcut phantom_dominance_action_shortcut
