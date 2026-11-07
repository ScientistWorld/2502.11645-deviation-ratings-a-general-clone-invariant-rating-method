#!/bin/bash
# Reproduce the reference end to end from the final code: paper artifacts and
# uniform baseline, the standard evaluation (scripts/evaluate.sh), the train
# slice and the hidden test (all three call the rating program scripts/rate.sh
# once per population iteration), and validation. About 15 minutes on one CPU.
#
# This job (iteration 13) also replays the reference, the honest variants and the
# fixed shortcuts through the hardened hidden test (redteam/hardening_final/,
# about 45 minutes) and scores the REDTEAM's public three-LP witness.
set -euo pipefail
cd /home/user
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1

bash scripts/reproduce.sh
bash scripts/evaluate_train.sh
bash scripts/evaluate_test.sh
python3 validate.py

python3 redteam/hardening_final/witness.py || echo "witness check failed"
python3 redteam/hardening_final/run_bundle.py || echo "replay bundle failed"
python3 redteam/hardening_final/summarize.py || echo "summary failed"
