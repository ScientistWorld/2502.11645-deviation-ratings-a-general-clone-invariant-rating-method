#!/usr/bin/env python3
"""
Visible train-slice evaluation for the deviation-rating benchmark.

This intentionally mirrors the contract of scripts/evaluate.sh: read existing
method artifacts from checkpoints/method and write a scores file under scoring/.
"""

from __future__ import annotations

import json
from itertools import product
from math import prod
from pathlib import Path
from typing import Iterable

from eval.split_common import SCORING_DIR, discover_method_dirs

ROOT = Path("/home/user")


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Required method artifact is missing: {path}")
    return json.loads(path.read_text())


def _rating(payload: dict, section: str | None, player: int, action: int) -> float:
    source = payload if section is None else payload[section]
    return float(source["ratings"][str(player)][str(action)])


def _action_values(payload: dict, section: str | None, player: int, count: int) -> list[float]:
    return [_rating(payload, section, player, action) for action in range(count)]


def _max_abs(values: Iterable[float]) -> float:
    values = list(values)
    return max((abs(value) for value in values), default=0.0)


def _round(value: float) -> float:
    return round(float(value), 8)


def augmented_biased_shapley_game() -> list:
    q = 241.0
    player0 = [
        [-8.0, -2.0, 4.0, -680.0 / q],
        [2.0, -8.0, -1.0, -680.0 / q],
        [-4.0, 1.0, -8.0, -680.0 / q],
        [-712.0 / q, -920.0 / q, -184.0 / q, -680.0 / q],
    ]
    player1 = [
        [-8.0, 2.0, -4.0, -712.0 / q],
        [-2.0, -8.0, 1.0, -920.0 / q],
        [4.0, -1.0, -8.0, -184.0 / q],
        [-680.0 / q, -680.0 / q, -680.0 / q, -680.0 / q],
    ]
    return [player0, player1]


def dominance_test_game() -> list:
    return [
        [[2.0, 2.0], [1.0, 1.0]],
        [[2.0, 1.0], [2.0, 1.0]],
    ]


def _payoff(payoffs: list, player: int, joint: Iterable[int]) -> float:
    value = payoffs[player]
    for action in joint:
        value = value[action]
    return float(value)


def cce_gap(payoffs: list, sigma: list[float], action_dims: list[int]) -> float:
    sigma_arr = [max(float(value), 0.0) for value in sigma]
    if len(sigma_arr) != prod(action_dims):
        raise ValueError(
            f"Equilibrium length {len(sigma_arr)} does not match action dimensions {action_dims}"
        )
    total_mass = sum(sigma_arr)
    if total_mass <= 0.0:
        raise ValueError("Equilibrium distribution has no positive mass")
    sigma_arr = [value / total_mass for value in sigma_arr]

    joint_actions = list(product(*[range(dim) for dim in action_dims]))
    total_gap = 0.0
    for player in range(len(action_dims)):
        deviations = []
        for action in range(action_dims[player]):
            gain = 0.0
            for probability, joint in zip(sigma_arr, joint_actions):
                deviated = list(joint)
                deviated[player] = action
                gain += probability * (_payoff(payoffs, player, deviated) - _payoff(payoffs, player, joint))
            deviations.append(gain)
        total_gap += max(0.0, max(deviations))
    return float(total_gap)


def evaluate_biased_shapley(method_dir: Path) -> dict[str, float]:
    payload = _load_json(method_dir / "biased_shapley_augmented.json")
    action_count = len(payload["action_names"])
    ratings = _action_values(payload, None, 0, action_count)
    return {
        "dev_gap": _round(max(ratings) - min(ratings)),
        "CCE_gap": _round(cce_gap(augmented_biased_shapley_game(), payload["equilibrium"], [4, 4])),
    }


def evaluate_clone_invariance(method_dir: Path) -> dict[str, float]:
    payload = _load_json(method_dir / "clone_invariance.json")
    diffs = [
        _rating(payload, "cloned", 0, action) - _rating(payload, "original", 0, action)
        for action in range(3)
    ]
    return {"max_diff": _round(_max_abs(diffs))}


def evaluate_mixture_invariance(method_dir: Path) -> dict[str, float]:
    payload = _load_json(method_dir / "mixture_invariance.json")
    diffs = []
    for player, action_count in ((0, 2), (1, 2)):
        for action in range(action_count):
            diffs.append(
                _rating(payload, "augmented", player, action)
                - _rating(payload, "base", player, action)
            )

    mixture = [float(value) for value in payload["mixture"]]
    expected = sum(mixture[action] * _rating(payload, "base", 0, action) for action in range(2))
    mixture_error = _rating(payload, "augmented", 0, 2) - expected
    return {
        "original_max_diff": _round(_max_abs(diffs)),
        "mixture_error": _round(abs(mixture_error)),
    }


def evaluate_offset_invariance(method_dir: Path) -> dict[str, float]:
    payload = _load_json(method_dir / "offset_invariance.json")
    diffs = []
    for player in (0, 1):
        for action in (0, 1):
            diffs.append(
                _rating(payload, "offset", player, action)
                - _rating(payload, "base", player, action)
            )
    return {"max_diff": _round(_max_abs(diffs))}


def evaluate_dominance_preserving(method_dir: Path) -> dict[str, float]:
    payload = _load_json(method_dir / "dominance_preserving.json")
    violations = 0
    for pair in payload["dominance_pairs"]:
        player = int(pair["player"])
        better = int(pair["better"])
        worse = int(pair["worse"])
        if _rating(payload, None, player, better) - _rating(payload, None, player, worse) < -1e-8:
            violations += 1
    return {
        "dominance_violations": violations,
        "CCE_gap": _round(cce_gap(dominance_test_game(), payload["equilibrium"], [2, 2])),
    }


def main() -> dict:
    SCORING_DIR.mkdir(parents=True, exist_ok=True)
    scores = {
        "experiments": {
            "biased_shapley_augmented": {"results": {}},
            "clone_invariance": {"results": {}},
            "mixture_invariance": {"results": {}},
            "offset_invariance": {"results": {}},
            "dominance_preserving": {"results": {}},
        }
    }
    for method_id, method_dir in discover_method_dirs().items():
        scores["experiments"]["biased_shapley_augmented"]["results"][method_id] = evaluate_biased_shapley(
            method_dir
        )
        scores["experiments"]["clone_invariance"]["results"][method_id] = evaluate_clone_invariance(
            method_dir
        )
        scores["experiments"]["mixture_invariance"]["results"][method_id] = evaluate_mixture_invariance(
            method_dir
        )
        scores["experiments"]["offset_invariance"]["results"][method_id] = evaluate_offset_invariance(
            method_dir
        )
        scores["experiments"]["dominance_preserving"]["results"][method_id] = (
            evaluate_dominance_preserving(method_dir)
        )
    output_path = SCORING_DIR / "scores_train.json"
    output_path.write_text(json.dumps(scores, indent=2))
    print(json.dumps(scores, indent=2))
    return scores


if __name__ == "__main__":
    main()
