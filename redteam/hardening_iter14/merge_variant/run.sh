#!/bin/bash
set -euo pipefail
cd /home/user
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
exec python3 redteam/hardening_iter14/harness.py merge_variant "$@"
