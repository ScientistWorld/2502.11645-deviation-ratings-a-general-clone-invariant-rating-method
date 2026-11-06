#!/bin/bash
set -euo pipefail
cd /home/user
for shortcut in python_startup_shortcut global_rating_scale_shortcut masked_nan_ratings_shortcut masked_nan_strings_shortcut; do
  bash "redteam/${shortcut}/run.sh"
done > redteam/followup_job.log 2>&1
python3 redteam/summarize_shortcuts.py >> redteam/followup_job.log
