#!/bin/bash
# Job script submitted via the end-of-turn YAML block.
#
# These are post-hoc scorers over existing method artifacts, so this job is
# CPU-only and simply refreshes scoring/scores_{train,test}.json.

set -euo pipefail

cd /home/user

bash scripts/evaluate_train.sh
bash scripts/evaluate_test.sh
