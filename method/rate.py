"""Rating entrypoint used by every evaluator: ``python3 -m method.rate GAMES OUT``.

Reads ``{"games": [{"id", "payoffs"}]}`` (payoffs nested as [N, A_1, ..., A_N]),
computes deviation ratings with the sequential LP of Algorithm 1
(method/deviation_rating.py), and writes
``{"results": {id: {"ratings": [[...] per player], "equilibrium": [flat C-order]}}}``.
The equilibrium is the final LP's distribution, under which every rating is the
corresponding deviation gain.

Games of the noisy-redundancy experiment also carry ``noise_bound``. As in the
paper, the reference rates the observed payoffs as given (it does not return the
optional estimated ``payoffs``), so its ratings are the deviation ratings of the
observation.
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

import numpy as np

from method.deviation_rating import deviation_rating


def rate_game(payoffs) -> dict:
    array = np.asarray(payoffs, dtype=float)
    num_players = array.shape[0]
    action_dims = list(array.shape[1:])
    if array.ndim != num_players + 1:
        raise ValueError(f"payoff array of shape {array.shape} is not [N, A_1, ..., A_N]")
    result = deviation_rating(array, num_players, action_dims)
    ratings = [
        [float(result["ratings_dict"][p][a]) for a in range(action_dims[p])] for p in range(num_players)
    ]
    equilibrium = [float(x) for x in np.asarray(result["equilibrium"], dtype=float).reshape(-1)]
    return {"ratings": ratings, "equilibrium": equilibrium}


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: python3 -m method.rate GAMES_JSON RATINGS_JSON", file=sys.stderr)
        return 2
    spec = json.loads(Path(argv[1]).read_text())
    results = {}
    for game in spec["games"]:
        try:
            results[game["id"]] = rate_game(game["payoffs"])
        except Exception:  # one bad game must not hide the others
            print(f"rating failed for game {game.get('id')}:", file=sys.stderr)
            traceback.print_exc()
    Path(argv[2]).write_text(json.dumps({"results": results}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
