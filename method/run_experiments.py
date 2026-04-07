from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from data.game_data import (
    augmented_biased_shapley_game,
    cloned_first_action_game,
    construct_livebench_three_player_game,
    load_livebench_task_table,
    rock_paper_scissors,
)
from method.deviation_rating import cce_gap, deviation_rating


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def run_shapley(output_dir: Path) -> None:
    payoffs, action_names, meta = augmented_biased_shapley_game()
    result = deviation_rating(payoffs, 2, [4, 4])
    payload = {
        "experiment": "biased_shapley_augmented",
        "action_names": action_names,
        "meta": meta,
        "ratings": result["ratings_dict"],
        "equilibrium": result["equilibrium"].tolist(),
        "n_iterations": result["n_iterations"],
        "cce_gap": cce_gap(payoffs, np.array(result["equilibrium"]), 2, [4, 4]),
    }
    _write_json(output_dir / "biased_shapley_augmented.json", payload)


def run_clone(output_dir: Path) -> None:
    payoffs, action_names, meta = rock_paper_scissors()
    orig = deviation_rating(payoffs, 2, [3, 3])
    cloned_payoffs = cloned_first_action_game(payoffs)
    cloned = deviation_rating(cloned_payoffs, 2, [4, 3])
    _write_json(
        output_dir / "clone_invariance.json",
        {
            "experiment": "clone_invariance",
            "action_names": action_names,
            "meta": meta,
            "original": {
                "ratings": orig["ratings_dict"],
                "equilibrium": orig["equilibrium"].tolist(),
                "cce_gap": cce_gap(payoffs, np.array(orig["equilibrium"]), 2, [3, 3]),
            },
            "cloned": {
                "ratings": cloned["ratings_dict"],
                "equilibrium": cloned["equilibrium"].tolist(),
                "cce_gap": cce_gap(cloned_payoffs, np.array(cloned["equilibrium"]), 2, [4, 3]),
            },
        },
    )


def run_livebench(output_dir: Path, csv_path: Path) -> None:
    scores, models, tasks = load_livebench_task_table(csv_path)
    payoffs, action_dims = construct_livebench_three_player_game(scores)
    result = deviation_rating(payoffs, 3, action_dims)
    _write_json(
        output_dir / "livebench_three_player.json",
        {
            "experiment": "llm_rating_livebench",
            "models": models,
            "tasks": tasks,
            "ratings": result["ratings_dict"],
            "equilibrium": result["equilibrium"].tolist(),
            "n_iterations": result["n_iterations"],
            "cce_gap": cce_gap(payoffs, np.array(result["equilibrium"]), 3, action_dims),
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="/home/user/checkpoints/method")
    parser.add_argument("--livebench-csv", default="/home/user/data/livebench/all_tasks_2024-09-30.csv")
    parser.add_argument(
        "--experiments",
        nargs="+",
        default=["biased_shapley_augmented", "clone_invariance"],
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    for experiment in args.experiments:
        if experiment == "biased_shapley_augmented":
            run_shapley(output_dir)
        elif experiment == "clone_invariance":
            run_clone(output_dir)
        elif experiment == "llm_rating_livebench":
            run_livebench(output_dir, Path(args.livebench_csv))
        else:
            raise ValueError(f"Unknown experiment: {experiment}")


if __name__ == "__main__":
    main()
