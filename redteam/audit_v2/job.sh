#!/bin/bash
# Run reference seed checks and shortcut trials on the CPU job node.
set -euo pipefail
cd /home/user
export PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
python3 redteam/audit_v2/run_job.py
