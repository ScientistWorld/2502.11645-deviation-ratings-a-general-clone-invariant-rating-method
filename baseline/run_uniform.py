from __future__ import annotations

import json
from pathlib import Path

from data.game_data import augmented_biased_shapley_game
from method.deviation_rating import uniform_rating


def main() -> None:
    payoffs, action_names, meta = augmented_biased_shapley_game()
    result = uniform_rating(payoffs, 2, [4, 4])
    payload = {
        "experiment": "biased_shapley_augmented",
        "action_names": action_names,
        "meta": meta,
        "ratings": result,
    }
    output_path = Path("/home/user/checkpoints/baseline/uniform_biased_shapley.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
