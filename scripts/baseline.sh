#!/bin/bash
# Run baseline methods (uniform averaging) for comparison.
#
# Usage:
#   bash scripts/baseline.sh

set -e

cd /home/user
export PYTHONPATH="/home/user${PYTHONPATH:+:$PYTHONPATH}"

python3 -m baseline.run_uniform
