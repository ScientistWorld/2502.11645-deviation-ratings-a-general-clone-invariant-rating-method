#!/bin/bash
# Job script submitted via the end-of-turn YAML block.
#
# The split evaluators score the already-generated method artifacts under
# /home/user/checkpoints and refresh scoring/scores_{train,test}.json.

set -e

cd /home/user

bash scripts/evaluate_train.sh
bash scripts/evaluate_test.sh
