#!/bin/bash
# Reproduce the reference end to end from the final code: paper artifacts and
# uniform baseline, the standard evaluation (scripts/evaluate.sh), the train
# slice and the hidden test (all three call the rating program scripts/rate.sh
# once per population iteration), and validation. About 15 minutes on one CPU.
#
# The hardening audit is separate:
#   python3 redteam/hardening_final/witness.py      the REDTEAM's public three-LP witness
#   python3 redteam/hardening_final/run_bundle.py   reference, honest variants and fixed
#                                                   shortcuts through the hidden test
#                                                   (about 35 minutes, resumable)
#   python3 redteam/hardening_final/summarize.py    before/after comparison
# Iteration 12's full replay of 65 shortcuts is python3 redteam/replay_all.py.
set -euo pipefail
cd /home/user
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1

bash scripts/reproduce.sh
bash scripts/evaluate_train.sh
bash scripts/evaluate_test.sh
python3 validate.py
