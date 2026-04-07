#!/bin/bash
# Job script submitted via the end-of-turn YAML block.
#
# This runs inside the compute container with:
#   - Your workspace mounted at /home/user
#   - GPU(s) available (game theory computation is CPU-bound)
#   - No internet access
#
# This paper involves CPU-only linear programming.

set -e

cd /home/user

# Run the full reproduction pipeline
bash scripts/reproduce.sh
