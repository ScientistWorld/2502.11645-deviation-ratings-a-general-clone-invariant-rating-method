#!/bin/bash
# Run the deviation rating method (paper's proposed approach).
#
# Usage:
#   bash scripts/method.sh

set -e

cd /home/user

# Run evaluation which includes the deviation rating method
bash scripts/evaluate.sh
