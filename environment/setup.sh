#!/bin/bash
set -euo pipefail
TASK_SETUP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
uv pip install --system --no-index --find-links "$TASK_SETUP_ROOT/redteam/packages" numpy==2.2.6 scipy==1.15.3
