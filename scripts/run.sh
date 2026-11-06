#!/bin/bash
set -euo pipefail
cd /home/user
mkdir -p redteam/reference
bash scripts/evaluate_test.sh > redteam/reference/initial_test.log 2>&1
cp scoring/scores_test.json redteam/reference/initial_scores_test.json
cp redteam/reference/packaged_scores_test.json scoring/scores_test.json
python3 - <<'PYENV'
import json, platform
import numpy, scipy
from pathlib import Path
Path('redteam/reference/environment.json').write_text(json.dumps({'python': platform.python_version(), 'numpy': numpy.__version__, 'scipy': scipy.__version__, 'reference_evaluation': 'completed'}, indent=2) + '\n')
PYENV
