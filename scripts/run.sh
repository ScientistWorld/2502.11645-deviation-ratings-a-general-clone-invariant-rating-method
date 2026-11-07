#!/bin/bash
# Hardening job 1 (diagnostic): reference end to end on the rating-program
# contract, hidden test, diagnostics sweep, and every shortcut replay.
set -uo pipefail
cd /home/user
python3 -c "import sys, numpy, scipy; print(sys.version); print('numpy', numpy.__version__, 'scipy', scipy.__version__)"
echo "=== reproduce (method, baseline, evaluate, validate --compare)"
time bash scripts/reproduce.sh
echo "=== train"
time bash scripts/evaluate_train.sh
echo "=== hidden test"
time bash scripts/evaluate_test.sh
echo "=== validate"
python3 validate.py
echo "=== diagnostics"
time python3 redteam/diagnostics.py
echo "=== shortcut replays"
time bash redteam/run_shortcuts.sh
echo "=== done"
