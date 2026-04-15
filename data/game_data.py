"""
Method-agnostic game and benchmark tables used by both method and evaluation code.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

import csv
import numpy as np


def augmented_biased_shapley_game() -> Tuple[np.ndarray, List[str], Dict[str, str]]:
    """
    Table 2 from the paper: biased Shapley game augmented with the Nash strategy N.
    """
    q = 241.0
    player0 = np.array(
        [
            [-8.0, -2.0, 4.0, -680.0 / q],
            [2.0, -8.0, -1.0, -680.0 / q],
            [-4.0, 1.0, -8.0, -680.0 / q],
            [-712.0 / q, -920.0 / q, -184.0 / q, -680.0 / q],
        ],
        dtype=float,
    )
    player1 = np.array(
        [
            [-8.0, 2.0, -4.0, -712.0 / q],
            [-2.0, -8.0, 1.0, -920.0 / q],
            [4.0, -1.0, -8.0, -184.0 / q],
            [-680.0 / q, -680.0 / q, -680.0 / q, -680.0 / q],
        ],
        dtype=float,
    )
    payoffs = np.stack([player0, player1], axis=0)
    return payoffs, ["R", "P", "S", "N"], {"source": "paper_table_2"}


def rock_paper_scissors() -> Tuple[np.ndarray, List[str], Dict[str, str]]:
    payoff_matrix = np.array(
        [
            [0.0, -1.0, 1.0],
            [1.0, 0.0, -1.0],
            [-1.0, 1.0, 0.0],
        ],
        dtype=float,
    )
    return np.stack([payoff_matrix, -payoff_matrix], axis=0), ["R", "P", "S"], {"source": "constructed"}


def cloned_first_action_game(payoffs: np.ndarray) -> np.ndarray:
    """
    Clone the first action for player 0 only.
    """
    cloned = np.zeros((payoffs.shape[0], payoffs.shape[1] + 1, payoffs.shape[2]), dtype=float)
    cloned[:, : payoffs.shape[1], :] = payoffs
    cloned[:, payoffs.shape[1], :] = payoffs[:, 0, :]
    return cloned


def general_sum_reference_game() -> Tuple[np.ndarray, List[str], Dict[str, str]]:
    """
    Small 2x2 general-sum game with non-equal deviation ratings.

    This game is used for paper property checks where mixture/offset invariance
    are more informative than on cyclic games with all-equal ratings.
    """
    player0 = np.array([[3.0, 0.0], [2.0, 1.0]], dtype=float)
    player1 = np.array([[0.0, 1.0], [2.0, 3.0]], dtype=float)
    return (
        np.stack([player0, player1], axis=0),
        ["A0", "A1"],
        {"source": "constructed_general_sum_reference"},
    )


def add_mixed_strategy_for_player(
    payoffs: np.ndarray,
    mixture: np.ndarray,
    player: int = 0,
) -> np.ndarray:
    """
    Add one strategy that is a fixed mixture over an existing player's actions.
    """
    action_dims = list(payoffs.shape[1:])
    if mixture.shape != (action_dims[player],):
        raise ValueError("Mixture weights must match the chosen player's action count")

    new_dims = action_dims[:]
    new_dims[player] += 1
    augmented = np.zeros((payoffs.shape[0],) + tuple(new_dims), dtype=float)

    slices = tuple(slice(0, dim) for dim in action_dims)
    augmented[(slice(None),) + slices] = payoffs

    for joint in np.ndindex(*new_dims):
        if joint[player] != new_dims[player] - 1:
            continue
        other_joint = joint[:player] + joint[player + 1 :]
        for p in range(payoffs.shape[0]):
            if p == player:
                # Mixed strategy payoff for the acting player.
                values = []
                for action in range(action_dims[player]):
                    source_joint = list(joint)
                    source_joint[player] = action
                    values.append(payoffs[(p,) + tuple(source_joint)])
                augmented[(p,) + joint] = float(np.dot(mixture, np.array(values, dtype=float)))
            else:
                # Other players also observe the mixed action in the same row/column.
                values = []
                for action in range(action_dims[player]):
                    source_joint = list(joint)
                    source_joint[player] = action
                    values.append(payoffs[(p,) + tuple(source_joint)])
                augmented[(p,) + joint] = float(np.dot(mixture, np.array(values, dtype=float)))

    return augmented


def add_offset(
    payoffs: np.ndarray,
    offsets: List[np.ndarray],
) -> np.ndarray:
    """
    Add arbitrary b_p(a_-p) offsets, which should not change deviation ratings.
    """
    adjusted = payoffs.copy()
    action_dims = payoffs.shape[1:]
    for p in range(payoffs.shape[0]):
        expected_shape = action_dims[:p] + action_dims[p + 1 :]
        if offsets[p].shape != expected_shape:
            raise ValueError(f"Offset {p} must have shape {expected_shape}, got {offsets[p].shape}")
        for joint in np.ndindex(*action_dims):
            other_joint = joint[:p] + joint[p + 1 :]
            adjusted[(p,) + joint] += float(offsets[p][other_joint])
    return adjusted


def dominance_test_game() -> Tuple[np.ndarray, List[str], Dict[str, str]]:
    """
    2x2 game where action 0 strictly dominates action 1 for both players.
    """
    player0 = np.array([[2.0, 2.0], [1.0, 1.0]], dtype=float)
    player1 = np.array([[2.0, 1.0], [2.0, 1.0]], dtype=float)
    return (
        np.stack([player0, player1], axis=0),
        ["D0", "D1"],
        {"source": "constructed_dominance_test"},
    )


def load_livebench_task_table(csv_path: str | Path) -> Tuple[np.ndarray, List[str], List[str]]:
    """
    Load a model-task score table where the first column is the model name.
    """
    csv_path = Path(csv_path)
    with csv_path.open("r", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        tasks = header[1:]
        models = []
        rows = []
        for row in reader:
            if not row:
                continue
            models.append(row[0])
            rows.append([float(value) for value in row[1:]])
    return np.array(rows, dtype=float), models, tasks


def construct_livebench_three_player_game(model_scores: np.ndarray) -> Tuple[np.ndarray, List[int]]:
    """
    Construct the 3-player model vs model vs task game described in Section 5.2.
    """
    n_models, n_tasks = model_scores.shape
    payoffs = np.zeros((3, n_models, n_models, n_tasks), dtype=float)
    for a in range(n_models):
        for b in range(n_models):
            diff = model_scores[a] - model_scores[b]
            payoffs[0, a, b, :] = diff
            payoffs[1, a, b, :] = -diff
            payoffs[2, a, b, :] = np.abs(diff)
    return payoffs, [n_models, n_models, n_tasks]
