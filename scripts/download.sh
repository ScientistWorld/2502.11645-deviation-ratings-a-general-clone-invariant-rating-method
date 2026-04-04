#!/bin/bash
# Download all data and models needed for this environment.
#
# This paper uses game-theoretic computation (no external datasets needed).
# All game data is generated programmatically.
#
# Estimated total download size: 0 MB
# Estimated disk usage: 0 MB

set -e

cd /home/user

# No external downloads required.
# All game data (Shapley game, Livebench approximations, etc.)
# is generated programmatically in method/game_generators.py.

echo "No external downloads needed — all game data is generated programmatically."
