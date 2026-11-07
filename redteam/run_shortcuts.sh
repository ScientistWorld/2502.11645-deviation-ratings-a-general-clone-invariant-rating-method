#!/bin/bash
# Replay the reference (three identical runs) and every shortcut through the
# hidden test, then summarise. Each replay restores the workspace afterwards.
set -euo pipefail
cd /home/user
for run in 0 1 2; do
  python3 redteam/shortcut_harness.py --reference-run "${run}"
done
python3 - <<'PY'
import json, subprocess
from pathlib import Path
for shortcut in json.loads(Path('redteam/shortcut_cases.json').read_text()):
    subprocess.run(['python3', 'redteam/shortcut_harness.py', '--shortcut', shortcut], check=True)
PY
python3 redteam/summarize_shortcuts.py
