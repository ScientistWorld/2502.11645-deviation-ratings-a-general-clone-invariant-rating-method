#!/bin/bash
# Evaluation script — the standard way to evaluate work in this environment.
#
# Runs the rating program scripts/rate.sh on the five documented public games
# and writes scoring/scores.json (same protocol as the visible train slice).

set -e

cd /home/user
mkdir -p scoring

# -I: ignore PYTHONPATH, user site-packages and the working directory.
exec python3 -I eval/evaluate.py
