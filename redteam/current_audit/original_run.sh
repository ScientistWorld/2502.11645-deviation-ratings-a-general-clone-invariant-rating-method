#!/bin/bash
# Reproduce the reference end to end from the final code: paper artifacts and
# uniform baseline, the standard evaluation (scripts/evaluate.sh), the train
# slice and the hidden test (all three call the rating program scripts/rate.sh
# once per population iteration), and validation. About 15 minutes on one CPU.
#
# The hardening audit is separate: python3 redteam/replay_all.py replays the
# reference and every shortcut in redteam/ through the hidden test (about two
# hours; it resumes across jobs), and python3 redteam/summarize_final.py
# compares them. Diagnostics: redteam/property_diagnostics.py,
# redteam/population_diagnostics.py.
set -euo pipefail
cd /home/user
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1

bash scripts/reproduce.sh
bash scripts/evaluate_train.sh
bash scripts/evaluate_test.sh
python3 validate.py
