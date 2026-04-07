#!/bin/bash
# Evaluation script — the standard way to evaluate work in this environment.
#
# This script runs all evaluation experiments and writes scoring/scores.json.
#
# OUTPUT: scoring/scores.json with per-experiment, per-method results.

set -e

cd /home/user
export PYTHONPATH="/home/user:/home/user/pkgs:/home/user/test_pkgs${PYTHONPATH:+:$PYTHONPATH}"

mkdir -p scoring

python3 -m eval.evaluate

echo "Evaluation complete. Results written to scoring/scores.json"
