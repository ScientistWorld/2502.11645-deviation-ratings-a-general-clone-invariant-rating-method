#!/bin/bash
# Job script submitted via the end-of-turn YAML block.
#
# Run the packaged reproduction end to end, then refresh the train/test split
# on the freshly generated artifacts and validate both scoring paths.

set -euo pipefail

cd /home/user

bash scripts/reproduce.sh
bash scripts/evaluate_train.sh
bash scripts/evaluate_test.sh
python3 validate.py
