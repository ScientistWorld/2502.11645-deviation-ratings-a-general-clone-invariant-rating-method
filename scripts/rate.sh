#!/bin/bash
# Rating-method entrypoint. Every evaluator (scripts/evaluate.sh,
# scripts/evaluate_train.sh and the hidden scripts/evaluate_test.sh) scores the
# method by running this program on games it supplies:
#
#   bash scripts/rate.sh GAMES_JSON RATINGS_JSON
#
# GAMES_JSON:   {"games": [{"id": ..., "payoffs": [N][A_1]...[A_N]}, ...]}
#               (noisy observations also carry "noise_bound": b)
# RATINGS_JSON: {"results": {id: {"ratings": [[r_p(a) ...] per player],
#                                 "equilibrium": [flat C-order joint distribution]}}}
#               (for a noisy observation, optionally "payoffs": the rated game,
#                every entry within b of the observed payoffs)
#
# Contract and validity checks: briefing/evaluation.md and eval/protocol.py.

set -euo pipefail

cd /home/user
export PYTHONPATH="/home/user${PYTHONPATH:+:$PYTHONPATH}"

exec python3 -m method.rate "$1" "$2"
