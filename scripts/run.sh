#!/bin/bash
# Reproduce the reference end to end from the final code: paper artifacts and
# uniform baseline, the standard evaluation (scripts/evaluate.sh), the train
# slice and the hidden test (all three call the rating program scripts/rate.sh),
# and validation. (Job 6 also replays, against the final hidden test, the cases
# whose earlier replay hit a system-file false positive; the full audit is
# python3 redteam/replay_all.py.)
set -uo pipefail
cd /home/user
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
OUT=redteam/job6
mkdir -p "$OUT"

bash scripts/reproduce.sh > "$OUT/reproduce.log" 2>&1; tail -3 "$OUT/reproduce.log"
bash scripts/evaluate_train.sh > "$OUT/train.log" 2>&1; grep -E "==|FAILED|deviation_rating|uniform_payoff  " "$OUT/train.log" | cut -c1-250
timeout 1500 bash scripts/evaluate_test.sh > "$OUT/test.log" 2>&1; cat "$OUT/test.log"
python3 validate.py > "$OUT/validate.log" 2>&1; tail -18 "$OUT/validate.log"

# No pipes here: the hidden test stops every non-ancestor process of the job.
timeout 2400 python3 redteam/replay_all.py --budget 2100 \
  --only reference,detached_rewriter_shortcut,mixture_original_drift_shortcut,negative_tolerance_shortcut,onehot_mixture_shortcut \
  > "$OUT/replays.log" 2>&1
cut -c1-300 "$OUT/replays.log"
python3 redteam/summarize_final.py > "$OUT/summary.txt" 2>&1; cat "$OUT/summary.txt"
echo "=== done after ${SECONDS}s"
