#!/bin/bash
set -euo pipefail
cd /home/user
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
exec python3 redteam/audit_20261107/harness.py feasibility_only_shortcut "$@"
