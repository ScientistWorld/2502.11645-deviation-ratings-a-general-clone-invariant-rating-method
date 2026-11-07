#!/bin/bash
# Hardening job 5: continue the shortcut replays through the final hidden test
# (redteam/replay_all.py skips cases already replayed against the same test).
set -uo pipefail
cd /home/user
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
OUT=redteam/job5
mkdir -p "$OUT"
# No pipes here: the hidden test stops every non-ancestor process of the job.
timeout 3450 python3 redteam/replay_all.py --budget 3150 > "$OUT/replays.log" 2>&1
cut -c1-400 "$OUT/replays.log"
python3 redteam/summarize_final.py > "$OUT/summary.txt" 2>&1; cat "$OUT/summary.txt"
echo "=== done after ${SECONDS}s"
