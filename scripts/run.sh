#!/bin/bash
# Job script submitted via the end-of-turn YAML block.
#
# TEMPORARY (hardening job 1): population-improvement diagnostics and timing of
# the new evaluators. The final version reproduces the reference end to end.

set -uo pipefail

cd /home/user

echo "=== population diagnostics"
time python3 redteam/population_diagnostics.py 2>&1 | tee redteam/population_diagnostics.log
echo "=== hidden test"
time bash scripts/evaluate_test.sh 2>&1 | tee redteam/job1_test.log
echo "=== train"
time bash scripts/evaluate_train.sh 2>&1 | tee redteam/job1_train.log
