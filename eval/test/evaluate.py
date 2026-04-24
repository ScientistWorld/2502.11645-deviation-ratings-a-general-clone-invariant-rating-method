#!/usr/bin/env python3
"""
Held-out test-slice evaluation for the deviation-rating benchmark.

The script reads the same pre-generated method artifacts as eval/train but
checks complementary properties that are not scored by the visible train slice.
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


def _max_abs(values: Iterable[float]) -> float:
    values = list(values)
    return max((abs(value) for value in values), default=0.0)


def _round(value: float) -> float:
    return round(float(value), 8)


def _uniform_joint(action_dims: list[int]) -> list[float]:
    mass = 1.0 / prod(action_dims)
    return [mass for _ in range(prod(action_dims))]


def _uniform_action_ratings(payoffs: list, action_dims: list[int]) -> dict[int, list[float]]:
    if len(action_dims) != 2:
        raise ValueError(f"Only 2-player games are supported, got {action_dims}")

    rows, cols = action_dims
    player0 = [sum(float(payoffs[0][row][col]) for col in range(cols)) / cols for row in range(rows)]
    player1 = [sum(float(payoffs[1][row][col]) for row in range(rows)) / rows for col in range(cols)]
    return {0: player0, 1: player1}


def _negative_uniform_action_ratings(payoffs: list, action_dims: list[int]) -> dict[int, list[float]]:
    ratings = _uniform_action_ratings(payoffs, action_dims)
    return {
        player: [-value for value in player_ratings]
        for player, player_ratings in ratings.items()
    }


def _zero_action_ratings(action_dims: list[int]) -> dict[int, list[float]]:
    return {player: [0.0 for _ in range(count)] for player, count in enumerate(action_dims)}


def _player_centered(ratings: dict[int, list[float]]) -> dict[int, list[float]]:
    centered = {}
    for player, player_ratings in ratings.items():
        mean_value = sum(player_ratings) / len(player_ratings)
        centered[player] = [value - mean_value for value in player_ratings]
    return centered


def _max_abs_action_delta(
    before: dict[int, list[float]],
    after: dict[int, list[float]],
    players: Iterable[int],
) -> float:
    diffs = []
    for player in players:
        for action, value in enumerate(before[player]):
            diffs.append(after[player][action] - value)
    return _max_abs(diffs)


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


def general_sum_reference_game() -> list:
    return [
        [[3.0, 0.0], [2.0, 1.0]],
        [[0.0, 1.0], [2.0, 3.0]],
    ]


def _zeros_2p(action_dims: list[int]) -> list:
    return [
        [[0.0 for _ in range(action_dims[1])] for _ in range(action_dims[0])]
        for _ in range(2)
    ]


def _payoff(payoffs: list, player: int, joint: Iterable[int]) -> float:
    value = payoffs[player]
    for action in joint:
        value = value[action]
    return float(value)


def _set_payoff(payoffs: list, player: int, joint: Iterable[int], value: float) -> None:
    first, second = list(joint)
    payoffs[player][first][second] = float(value)


def add_mixed_strategy_for_player(payoffs: list, mixture: list[float], player: int) -> list:
    action_dims = [len(payoffs[0]), len(payoffs[0][0])]
    new_dims = action_dims[:]
    new_dims[player] += 1
    augmented = _zeros_2p(new_dims)

    for joint in product(*[range(dim) for dim in new_dims]):
        source_is_original = joint[player] < action_dims[player]
        for payoff_player in range(2):
            if source_is_original:
                _set_payoff(augmented, payoff_player, joint, _payoff(payoffs, payoff_player, joint))
                continue
            mixed_value = 0.0
            for action in range(action_dims[player]):
                source_joint = list(joint)
                source_joint[player] = action
                mixed_value += mixture[action] * _payoff(payoffs, payoff_player, source_joint)
            _set_payoff(augmented, payoff_player, joint, mixed_value)
    return augmented


def add_offset(payoffs: list, offsets: list[list[float]]) -> list:
    action_dims = [len(payoffs[0]), len(payoffs[0][0])]
    adjusted = _zeros_2p(action_dims)
    for player in range(2):
        for joint in product(*[range(dim) for dim in action_dims]):
            other_joint = joint[:player] + joint[player + 1 :]
            _set_payoff(
                adjusted,
                player,
                joint,
                _payoff(payoffs, player, joint) + float(offsets[player][other_joint[0]]),
            )
    return adjusted


def dominance_test_game() -> list:
    return [
        [[2.0, 2.0], [1.0, 1.0]],
        [[2.0, 1.0], [2.0, 1.0]],
    ]


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
    all_ratings = [
        _rating(payload, None, player, action)
        for player in (0, 1)
        for action in range(action_count)
    ]
    symmetry_diffs = [
        _rating(payload, None, 0, action) - _rating(payload, None, 1, action)
        for action in range(action_count)
    ]
    return {
        "all_player_dev_gap": _round(max(all_ratings) - min(all_ratings)),
        "player_symmetry_gap": _round(_max_abs(symmetry_diffs)),
        "CCE_gap": _round(cce_gap(augmented_biased_shapley_game(), payload["equilibrium"], [4, 4])),
    }


def evaluate_clone_invariance(method_dir: Path) -> dict[str, float]:
    payload = _load_json(method_dir / "clone_invariance.json")
    diffs = []
    for player, action_count in ((0, 3), (1, 3)):
        for action in range(action_count):
            diffs.append(
                _rating(payload, "cloned", player, action)
                - _rating(payload, "original", player, action)
            )
    clone_source_gap = _rating(payload, "cloned", 0, 3) - _rating(payload, "cloned", 0, 0)
    return {
        "all_players_max_diff": _round(_max_abs(diffs)),
        "clone_source_gap": _round(abs(clone_source_gap)),
    }


def evaluate_mixture_invariance(method_dir: Path) -> dict[str, float]:
    payload = _load_json(method_dir / "mixture_invariance.json")
    base_game = general_sum_reference_game()
    mixture = [float(value) for value in payload["mixture"]]
    augmented_game = add_mixed_strategy_for_player(base_game, mixture, player=0)
    base_gap = cce_gap(base_game, payload["base"]["equilibrium"], [2, 2])
    augmented_gap = cce_gap(augmented_game, payload["augmented"]["equilibrium"], [3, 2])
    signed_error = _rating(payload, "augmented", 0, 2) - sum(
        float(mixture[action]) * _rating(payload, "base", 0, action) for action in range(2)
    )
    return {
        "mixture_error": _round(abs(signed_error)),
        "max_CCE_gap": _round(max(base_gap, augmented_gap)),
    }


def evaluate_offset_invariance(method_dir: Path) -> dict[str, float]:
    payload = _load_json(method_dir / "offset_invariance.json")
    base_game = general_sum_reference_game()
    offset_game = add_offset(
        base_game,
        [[10.0, -4.0], [7.0, -3.0]],
    )
    base_gap = cce_gap(base_game, payload["base"]["equilibrium"], [2, 2])
    offset_gap = cce_gap(offset_game, payload["offset"]["equilibrium"], [2, 2])
    base_ratings = {
        0: [_rating(payload, "base", 0, action) for action in (0, 1)],
        1: [_rating(payload, "base", 1, action) for action in (0, 1)],
    }
    offset_ratings = {
        0: [_rating(payload, "offset", 0, action) for action in (0, 1)],
        1: [_rating(payload, "offset", 1, action) for action in (0, 1)],
    }
    return {
        "max_diff": _round(
            _max_abs_action_delta(
                _player_centered(base_ratings),
                _player_centered(offset_ratings),
                players=(0, 1),
            )
        ),
        "max_CCE_gap": _round(max(base_gap, offset_gap)),
    }


def evaluate_dominance_preserving(method_dir: Path) -> dict[str, float]:
    payload = _load_json(method_dir / "dominance_preserving.json")
    margins = []
    violations = 0
    for pair in payload["dominance_pairs"]:
        player = int(pair["player"])
        better = int(pair["better"])
        worse = int(pair["worse"])
        margin = _rating(payload, None, player, better) - _rating(payload, None, player, worse)
        margins.append(margin)
        if margin <= 1e-8:
            violations += 1
    return {
        "dominance_violations": violations,
        "min_margin": _round(min(margins)),
        "CCE_gap": _round(cce_gap(dominance_test_game(), payload["equilibrium"], [2, 2])),
    }


def evaluate_offset_uniform_baseline() -> dict[str, float]:
    base_game = general_sum_reference_game()
    offset_game = add_offset(
        base_game,
        [[10.0, -4.0], [7.0, -3.0]],
    )
    base_ratings = _uniform_action_ratings(base_game, [2, 2])
    offset_ratings = _uniform_action_ratings(offset_game, [2, 2])
    return {
        "max_diff": _round(
            _max_abs_action_delta(
                _player_centered(base_ratings),
                _player_centered(offset_ratings),
                players=(0, 1),
            )
        ),
        "max_CCE_gap": _round(
            max(
                cce_gap(base_game, _uniform_joint([2, 2]), [2, 2]),
                cce_gap(offset_game, _uniform_joint([2, 2]), [2, 2]),
            )
        ),
    }


def evaluate_dominance_zero_baseline() -> dict[str, float]:
    ratings = _zero_action_ratings([2, 2])
    margins = []
    violations = 0
    for player in (0, 1):
        margin = ratings[player][0] - ratings[player][1]
        margins.append(margin)
        if margin <= 1e-8:
            violations += 1
    return {
        "dominance_violations": violations,
        "min_margin": _round(min(margins)),
        "CCE_gap": _round(cce_gap(dominance_test_game(), _uniform_joint([2, 2]), [2, 2])),
    }


def evaluate_dominance_negative_uniform_baseline() -> dict[str, float]:
    ratings = _negative_uniform_action_ratings(dominance_test_game(), [2, 2])
    margins = []
    violations = 0
    for player in (0, 1):
        margin = ratings[player][0] - ratings[player][1]
        margins.append(margin)
        if margin <= 1e-8:
            violations += 1
    return {
        "dominance_violations": violations,
        "min_margin": _round(min(margins)),
        "CCE_gap": _round(cce_gap(dominance_test_game(), _uniform_joint([2, 2]), [2, 2])),
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

    scores["experiments"]["offset_invariance"]["results"]["uniform_payoff"] = (
        evaluate_offset_uniform_baseline()
    )
    scores["experiments"]["dominance_preserving"]["results"]["zero_rating"] = (
        evaluate_dominance_zero_baseline()
    )
    scores["experiments"]["dominance_preserving"]["results"]["negative_uniform_payoff"] = (
        evaluate_dominance_negative_uniform_baseline()
    )
    output_path = SCORING_DIR / "scores_test.json"
    output_path.write_text(json.dumps(scores, indent=2))
    print(json.dumps(scores, indent=2))
    return scores


if __name__ == "__main__":
    main()
