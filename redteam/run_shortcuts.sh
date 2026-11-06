#!/bin/bash
set -euo pipefail
cd /home/user
for seed in 0 1 2; do
  bash "redteam/reference_seeds/seed_${seed}/run.sh"
done
python3 - <<'PY'
import json, subprocess
from pathlib import Path
for shortcut in json.loads(Path('redteam/shortcut_cases.json').read_text()):
    subprocess.run(['bash', f'redteam/{shortcut}/run.sh'], check=True)
PY
python3 redteam/summarize_shortcuts.py
