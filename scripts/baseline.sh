#!/bin/bash
# Run baseline methods (uniform averaging) for comparison.
#
# Usage:
#   bash scripts/baseline.sh

set -e

cd /home/user

# The baseline (uniform rating) is computed within eval/evaluate.py.
# Running evaluate.sh includes both deviation rating and baseline comparisons.
bash scripts/evaluate.sh
