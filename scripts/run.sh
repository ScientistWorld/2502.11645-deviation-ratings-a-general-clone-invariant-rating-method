#!/bin/bash
# Hardening job 1 (diagnostics): environment probe, the reference through the new
# train and hidden evaluators (timing), property and population diagnostics on
# non-hidden seeds, and replays of the five shortcuts REDTEAM.md found paying.
set -uo pipefail
cd /home/user
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
OUT=redteam/job1
mkdir -p "$OUT"

echo "=== environment"
{
  grep -E '^(NSpid|Uid)' /proc/self/status
  echo "pid1: $(stat -c %U /proc/1) $(tr '\0' ' ' < /proc/1/cmdline)"
  ps -eo pid,ppid,user,etimes,cmd 2>/dev/null || ls /proc | grep -c '^[0-9]'
  python3 -c "import numpy, scipy, sys; print(sys.version, numpy.__version__, scipy.__version__)"
  nproc
} > "$OUT/environment.txt" 2>&1
cat "$OUT/environment.txt"

echo "=== rating-program call overhead"
python3 - > "$OUT/call_overhead.txt" 2>&1 <<'PY'
import json, subprocess, tempfile, time, os
d = tempfile.mkdtemp()
open(f"{d}/g.json", "w").write(json.dumps({"games": [{"id": "a", "payoffs": [[[1, 0], [0, 1]], [[1, 0], [0, 1]]]}]}))
for i in range(5):
    t = time.time(); subprocess.run(["bash", "scripts/rate.sh", f"{d}/g.json", f"{d}/o.json"], check=True)
    print("call", i, round(time.time() - t, 3))
PY
cat "$OUT/call_overhead.txt"

echo "=== hidden test (reference)"
( time timeout 2400 bash scripts/evaluate_test.sh ) > "$OUT/test_reference.log" 2>&1
tail -40 "$OUT/test_reference.log"
cp scoring/scores_test.json "$OUT/scores_test_reference.json" 2>/dev/null

echo "=== train (reference)"
( time timeout 2400 bash scripts/evaluate_train.sh ) > "$OUT/train_reference.log" 2>&1
tail -12 "$OUT/train_reference.log"

echo "=== property diagnostics"
( time timeout 900 python3 redteam/property_diagnostics.py ) > "$OUT/property_diagnostics.log" 2>&1
tail -40 "$OUT/property_diagnostics.log"

echo "=== population diagnostics"
( time timeout 900 python3 redteam/population_diagnostics.py --iterations 128 --alt-iterations 64 --alt-seeds 2 ) \
  > "$OUT/population_diagnostics.log" 2>&1
tail -20 "$OUT/population_diagnostics.log"

echo "=== shortcut replays (REDTEAM's five)"
for name in lax_cce_shortcut zero_gain_fallback_shortcut batch_transport_shortcut \
            large_game_abandonment_shortcut prestarted_writer_shortcut; do
  timeout 900 python3 redteam/audit_v2/shortcut_harness.py "$name" --evidence-subdir job1_check \
    > "$OUT/replay_$name.log" 2>&1
  echo "$name exit=$?"
  python3 -c "
import json,sys
p='redteam/$name/job1_check/scores_test.json'
try:
    s=json.load(open(p))
    print({e: v['results']['deviation_rating'] for e, v in s['experiments'].items()})
except Exception as e: print('no scores', e)
"
done
echo "=== done"
