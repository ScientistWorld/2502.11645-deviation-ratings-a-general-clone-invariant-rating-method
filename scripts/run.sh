#!/bin/bash
# Hardening job 2 (diagnostics): the numerically robust reference through the
# hidden test (with the process sweep and stateless-call gate active), three
# shortcut replays, property diagnostics on the hidden and 4 alternative seeds,
# and population diagnostics (6 seeds, 256 iterations) to fix the horizon.
set -uo pipefail
cd /home/user
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
OUT=redteam/job2
mkdir -p "$OUT"

echo "=== hidden test (reference)"
( time timeout 1800 bash scripts/evaluate_test.sh ) > "$OUT/test_reference.log" 2>&1
tail -40 "$OUT/test_reference.log"
cp scoring/scores_test.json "$OUT/scores_test_reference.json" 2>/dev/null

echo "=== shortcut replays (test only)"
for name in prestarted_writer_shortcut zero_gain_fallback_shortcut large_game_abandonment_shortcut; do
  SHORTCUT_SKIP_TRAIN=1 timeout 900 python3 redteam/audit_v2/shortcut_harness.py "$name" --evidence-subdir job2_check \
    > "$OUT/replay_$name.log" 2>&1
  echo "$name exit=$?"
  grep -E "stopped|FAILED|gate failure" "redteam/$name/job2_check/test.log" | head -8
  python3 -c "
import json
p='redteam/$name/job2_check/scores_test.json'
try:
    s=json.load(open(p)); print({e: v['results']['deviation_rating'] for e, v in s['experiments'].items()})
except Exception as e: print('no scores', e)
print('marker', __import__('os').path.exists('redteam/$name/job2_check/shortcut_writer_ran.json'))
"
done

echo "=== property diagnostics"
( time timeout 1200 python3 redteam/property_diagnostics.py ) > "$OUT/property_diagnostics.log" 2>&1
tail -25 "$OUT/property_diagnostics.log"

echo "=== population diagnostics"
( time timeout 1500 python3 redteam/population_diagnostics.py --iterations 256 --alt-iterations 128 --alt-seeds 2 ) \
  > "$OUT/population_diagnostics.log" 2>&1
tail -20 "$OUT/population_diagnostics.log"
echo "=== done"
