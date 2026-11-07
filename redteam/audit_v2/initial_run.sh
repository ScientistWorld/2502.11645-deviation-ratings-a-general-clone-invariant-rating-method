#!/bin/bash
# Job script submitted via the end-of-turn YAML block.
#
# Reproduce the reference end to end: paper artifacts and uniform baseline,
# the public evaluation (scripts/evaluate.sh), the train slice, the hidden test
# (all three run the rating program scripts/rate.sh), and validation.
# The hardening audit (diagnostics and shortcut replays) is
# redteam/hardening_job.sh.

set -euo pipefail

cd /home/user

bash scripts/reproduce.sh
bash scripts/evaluate_train.sh
bash scripts/evaluate_test.sh
python3 validate.py
