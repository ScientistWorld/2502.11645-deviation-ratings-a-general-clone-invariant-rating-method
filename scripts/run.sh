#!/bin/bash
# Hardening job 4: diagnose job 3's stalled hidden test (the hidden seed's
# population loop rated in-process under a per-game alarm), the reference
# through the hidden test from the final code, validation, then as many shortcut
# replays as the time allows (redteam/replay_all.py resumes in later jobs).
set -uo pipefail
cd /home/user
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
OUT=redteam/job4
mkdir -p "$OUT"

echo "=== hidden population loop, in-process"
( time timeout 900 python3 redteam/hidden_population_check.py ) > "$OUT/hidden_population_check.log" 2>&1
tail -12 "$OUT/hidden_population_check.log"

echo "=== hidden test (reference)"
( time timeout 1500 bash scripts/evaluate_test.sh ) > "$OUT/test.log" 2>&1
echo "exit $?"
cat "$OUT/test.log"
python3 validate.py > "$OUT/validate.log" 2>&1; tail -20 "$OUT/validate.log"

echo "=== shortcut replays"
BUDGET=$(( 3250 - SECONDS - 300 ))
echo "replay budget ${BUDGET}s"
if [ "$BUDGET" -gt 120 ]; then
  # No pipes here: the hidden test stops every non-ancestor process of the job.
  timeout $(( BUDGET + 600 )) python3 redteam/replay_all.py --budget "$BUDGET" > "$OUT/replays.log" 2>&1
  cut -c1-600 "$OUT/replays.log"
fi
echo "=== done after ${SECONDS}s"
