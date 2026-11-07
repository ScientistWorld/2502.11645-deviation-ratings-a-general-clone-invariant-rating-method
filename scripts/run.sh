#!/bin/bash
# Temporary supplemental audit check; restore this file after the job.
set -euo pipefail
cd /home/user
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python3 redteam/current_audit/witness_check.py > redteam/current_audit/witness_job.log 2>&1
cat redteam/current_audit/witness_job.log
