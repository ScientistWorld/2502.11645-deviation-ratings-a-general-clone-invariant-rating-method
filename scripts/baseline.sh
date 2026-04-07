#!/bin/bash
# Run baseline methods (uniform averaging) for comparison.
#
# Usage:
#   bash scripts/baseline.sh

set -e

cd /home/user
export PYTHONPATH="/home/user:/home/user/test_pkgs${PYTHONPATH:+:$PYTHONPATH}"

python3 -m baseline.run_uniform
