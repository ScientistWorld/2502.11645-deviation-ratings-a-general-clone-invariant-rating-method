#!/bin/bash
# Reproduce the reference end to end from the final code: paper artifacts and
# uniform baseline, the standard evaluation (scripts/evaluate.sh), the train
# slice and the hidden test (all three call the rating program scripts/rate.sh
# once per population iteration), and validation. About 15 minutes on one CPU.
#
# This job (iteration 13) runs the hidden test first, then the REDTEAM's public
# three-LP witness, the replays of the reference, honest variants and fixed
# shortcuts through the hardened hidden test (redteam/hardening_final/, resumable),
# and finally the visible evaluations. Output goes through a relay that reports
# process states after 120 s of silence (a previous job stalled without output).
set -uo pipefail
cd /home/user
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
exec > >(python3 -I redteam/hardening_final/relay.py) 2>&1

step() { echo "=== $(date -u +%H:%M:%S) $*"; "$@" || echo "=== step failed (status $?): $*"; }

step timeout 2700 bash scripts/evaluate_test.sh
step timeout 600 python3 redteam/hardening_final/witness.py
step timeout 9000 python3 redteam/hardening_final/run_bundle.py
step timeout 300 python3 redteam/hardening_final/summarize.py
step timeout 1800 bash scripts/reproduce.sh
step timeout 1800 bash scripts/evaluate_train.sh
step python3 validate.py
echo "=== $(date -u +%H:%M:%S) run.sh finished"
