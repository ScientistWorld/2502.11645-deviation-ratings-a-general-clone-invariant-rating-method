#!/bin/bash
# Hardening job 3: property diagnostics (reference and cheap selections on the
# hidden and 4 alternative seeds), the reference end to end from the final code
# (paper artifacts, baseline, public/train/hidden evaluation, validation), then
# as many shortcut replays through the final hidden test as the time allows
# (redteam/replay_all.py resumes in later jobs).
set -uo pipefail
cd /home/user
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
OUT=redteam/job3
mkdir -p "$OUT"

echo "=== property diagnostics"
( time timeout 900 python3 redteam/property_diagnostics.py ) > "$OUT/property_diagnostics.log" 2>&1
grep -E "^\[|real" "$OUT/property_diagnostics.log" | cut -c1-400

echo "=== reference end to end"
( time bash scripts/reproduce.sh ) > "$OUT/reproduce.log" 2>&1
tail -5 "$OUT/reproduce.log"
( time bash scripts/evaluate_train.sh ) > "$OUT/train.log" 2>&1
grep -E "==|FAILED|gate failure|deviation_rating|real" "$OUT/train.log" | cut -c1-300
( time bash scripts/evaluate_test.sh ) > "$OUT/test.log" 2>&1
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
