#!/bin/bash
# reference_seed_1 installs and runs this candidate, then the exact hidden test.
set -euo pipefail
cd /home/user
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
exec python3 redteam/current_audit/harness.py reference_seed_1 "$@"
