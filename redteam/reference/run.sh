#!/bin/bash
set -euo pipefail
cd /home/user
for seed in 0 1 2; do
  python3 redteam/harness.py --reference "$seed"
done
