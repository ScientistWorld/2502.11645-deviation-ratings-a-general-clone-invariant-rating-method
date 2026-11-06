#!/bin/bash
set -euo pipefail
cd /home/user
bash redteam/run_shortcuts.sh > redteam/job.log 2>&1
