#!/bin/bash
# Job script submitted via the end-of-turn YAML block.
#
# This runs inside the compute container with:
#   - Your workspace mounted at /home/user
#   - GPU(s) available (game theory computation is CPU-bound)
#   - No internet access
#
# This paper involves game-theoretic LP computation — CPU only, no GPU needed.

set -e

cd /home/user

# Source PYTHONPATH setup if packages were installed via setup.sh
if [ -f /home/user/pkgs/activate.sh ]; then
    . /home/user/pkgs/activate.sh
fi

# Run the full reproduction pipeline
bash scripts/reproduce.sh
