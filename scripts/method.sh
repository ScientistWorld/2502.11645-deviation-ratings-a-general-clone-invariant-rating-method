#!/bin/bash
# Run the deviation rating method (paper's proposed approach).
#
# Usage:
#   bash scripts/method.sh

set -e

cd /home/user
export PYTHONPATH="/home/user:/home/user/test_pkgs${PYTHONPATH:+:$PYTHONPATH}"

python3 -m method.run_experiments --experiments biased_shapley_augmented clone_invariance
