#!/bin/bash
# Hardening job 2: reference end to end (method, baseline, public evaluation,
# train and hidden test, validation), then the hardening audit.
set -uo pipefail
cd /home/user
python3 -c "import sys, numpy, scipy; print(sys.version); print('numpy', numpy.__version__, 'scipy', scipy.__version__)"
bash scripts/reproduce.sh; echo "reproduce rc=$?"
bash scripts/evaluate_train.sh; echo "train rc=$?"
bash scripts/evaluate_test.sh; echo "test rc=$?"
python3 validate.py; echo "validate rc=$?"
bash redteam/hardening_job.sh
echo "=== done"
