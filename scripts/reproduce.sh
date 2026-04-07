#!/bin/bash
# Reproduce the paper's results end-to-end.
#
# This script runs inside the compute container.
# Assumes data is downloaded and container is built.

set -e

cd /home/user

bash scripts/method.sh
bash scripts/baseline.sh
bash scripts/evaluate.sh

# Display results
echo ""
echo "=== REPRODUCTION RESULTS ==="
echo "Results are in scoring/scores.json"
echo ""

# Compare with reference
python3 validate.py --compare
