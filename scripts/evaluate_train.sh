#!/bin/bash
# Visible train-slice evaluation for this benchmark.
#
# Runs the rating program scripts/rate.sh on the five documented public games
# and writes scoring/scores_train.json.

set -e

cd /home/user
mkdir -p scoring

# -I: ignore PYTHONPATH, user site-packages and the working directory.
exec python3 -I eval/train/evaluate.py
