#!/bin/bash
# Reproduce the reference end to end from the final code: paper artifacts and
# uniform baseline, the standard evaluation (scripts/evaluate.sh), the train
# slice and the hidden test (all three call the rating program scripts/rate.sh
# once per population iteration), and validation. About 25 minutes on one CPU.
#
# Iteration-14 verification (this job only): afterwards replay the reference
# (seed 0, and seed 1 with permuted action labels), the better variant (merging
# near-copies within the noise bound), the weaker one-LP ablation and the fixed
# shortcuts through the unchanged no-argument hidden test:
#   python3 redteam/hardening_iter14/run_bundle.py   (resumable)
#   python3 redteam/hardening_iter14/summarize.py    (ranks with scoring/reference.json)
set -euo pipefail
cd /home/user
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1

stamp() { echo "=== $(date +%H:%M:%S) $*"; }

stamp "reference: reproduce.sh (paper artifacts, baseline, standard evaluation, validate --compare)"
bash scripts/reproduce.sh
stamp "reference: train slice"
bash scripts/evaluate_train.sh
stamp "reference: hidden test"
bash scripts/evaluate_test.sh
stamp "validate.py"
python3 validate.py
mkdir -p redteam/hardening_iter14/reference_run
cp scoring/scores.json scoring/scores_train.json scoring/scores_test.json redteam/hardening_iter14/reference_run/

stamp "hardening replays"
python3 redteam/hardening_iter14/run_bundle.py
stamp "run.sh finished"
