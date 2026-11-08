#!/bin/bash
# Reproduce the reference end to end from the final code: paper artifacts and
# uniform baseline, the standard evaluation (scripts/evaluate.sh), the train
# slice and the hidden test (all three call the rating program scripts/rate.sh
# once per population iteration), and validation. About 25 minutes on one CPU.
#
# The iteration-14 hardening audit is separate (HARDENING.md):
#   python3 redteam/hardening_iter14/run_bundle.py    reference, better and weaker variants and the
#                                                     fixed shortcuts through the hidden test
#                                                     (about 2 hours, resumable)
#   python3 redteam/hardening_iter14/summarize.py     ranks with scoring/reference.json
#   python3 redteam/hardening_iter14/paired_noisy.py  exact paired per-instance comparison on the
#                                                     noisy-redundancy experiment (about 30 minutes)
set -euo pipefail
cd /home/user
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1

bash scripts/reproduce.sh
bash scripts/evaluate_train.sh
bash scripts/evaluate_test.sh
python3 validate.py
