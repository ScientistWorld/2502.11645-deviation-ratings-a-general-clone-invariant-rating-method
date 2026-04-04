#!/bin/bash
# Evaluation script — the standard way to evaluate work in this environment.
#
# This script runs all evaluation experiments and writes scoring/scores.json.
#
# OUTPUT: scoring/scores.json with per-experiment, per-method results.

set -e

cd /home/user

mkdir -p scoring

python3 -c "
import sys
sys.path.insert(0, 'eval')
from evaluate import main
results = main()
print('All evaluations completed.')
"

echo "Evaluation complete. Results written to scoring/scores.json"
