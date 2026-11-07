#!/bin/bash
# Temporary audit job entrypoint; restored after audit.
set -euo pipefail
cd /home/user
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python3 redteam/current_audit/run_bundle.py
