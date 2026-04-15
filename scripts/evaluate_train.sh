#!/bin/bash
# Visible train-slice evaluation for this benchmark.
#
# Mirrors scripts/evaluate.sh: read pre-generated method artifacts and write
# scoring/scores_train.json.

set -e

cd /home/user
export PYTHONPATH="/home/user:/home/user/pkgs:/home/user/test_pkgs${PYTHONPATH:+:$PYTHONPATH}"

mkdir -p scoring

python3 eval/train/evaluate.py

echo "Train evaluation complete. Results written to scoring/scores_train.json"
