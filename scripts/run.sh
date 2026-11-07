#!/bin/bash
# Confirm substantive scoring shortcuts on the CPU job node.
set -euo pipefail
cd /home/user
export PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
python3 redteam/audit_v2/followup_job.py
