#!/bin/bash
# Held-out test-slice evaluation for this benchmark.
#
# Mirrors scripts/evaluate.sh: read pre-generated method artifacts and write
# scoring/scores_test.json.

set -e

cd /home/user
export PYTHONPATH="/home/user:/home/user/pkgs:/home/user/test_pkgs${PYTHONPATH:+:$PYTHONPATH}"

mkdir -p scoring

python3 eval/test/evaluate.py

echo "Test evaluation complete. Results written to scoring/scores_test.json"
