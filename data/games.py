"""Exact game definitions used in this reproduction."""

from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np


def biased_shapley_base() -> Tuple[np.ndarray, List[str], Dict[str, str]]:
    """
    Paper's biased Shapley game over R, P, S.

    Table 2a has off-diagonal zero-sum interactions and diagonal coordination
    penalties of -8 for both players.
    """
    p0 = np.array(
        [
            [-8.0, -2.0, 4.0],
            [2.0, -8.0, -1.0],
            [-4.0, 1.0, -8.0],
        ]
    )
    p1 = np.array(
        [
            [-8.0, 2.0, -4.0],
            [-2.0, -8.0, 1.0],
            [4.0, -1.0, -8.0],
        ]
    )
    return np.stack([p0, p1], axis=0), ["R", "P", "S"], {"game_name": "biased_shapley_base"}


def biased_shapley_augmented() -> Tuple[np.ndarray, List[str], Dict[str, str]]:
    """
    Table 2a: biased Shapley game augmented with the Nash strategy N.

    The paper states the mixed Nash strategy is [87, 100, 54] / 241.
    """
    base_payoffs, base_names, _ = biased_shapley_base()
    mix = np.array([87.0, 100.0, 54.0]) / 241.0

    p0 = np.zeros((4, 4), dtype=float)
    p1 = np.zeros((4, 4), dtype=float)
    p0[:3, :3] = base_payoffs[0]
    p1[:3, :3] = base_payoffs[1]

    for i in range(3):
        p0[i, 3] = float(np.dot(base_payoffs[0][i], mix))
        p1[i, 3] = float(np.dot(base_payoffs[1][i], mix))
        p0[3, i] = float(np.dot(mix, base_payoffs[0][:, i]))
        p1[3, i] = float(np.dot(mix, base_payoffs[1][:, i]))

    p0[3, 3] = float(mix @ base_payoffs[0] @ mix)
    p1[3, 3] = float(mix @ base_payoffs[1] @ mix)

    return (
        np.stack([p0, p1], axis=0),
        base_names + ["N"],
        {"game_name": "biased_shapley_augmented"},
    )


def rock_paper_scissors() -> Tuple[np.ndarray, List[str], Dict[str, str]]:
    """Classic two-player zero-sum rock-paper-scissors."""
    payoff_matrix = np.array(
        [
            [0.0, -1.0, 1.0],
            [1.0, 0.0, -1.0],
            [-1.0, 1.0, 0.0],
        ]
    )
    return (
        np.stack([payoff_matrix, -payoff_matrix], axis=0),
        ["R", "P", "S"],
        {"game_name": "rock_paper_scissors"},
    )


def clone_strategy(
    payoffs: np.ndarray,
    player: int,
    action: int,
) -> np.ndarray:
    """Clone one player's action into a new action with identical payoffs."""
    action_dims = list(payoffs.shape[1:])
    new_dims = action_dims[:]
    new_dims[player] += 1
    cloned = np.zeros((payoffs.shape[0],) + tuple(new_dims), dtype=float)

    slices = tuple(slice(0, dim) for dim in action_dims)
    cloned[(slice(None),) + slices] = payoffs

    for index in np.ndindex(*new_dims):
        if index[player] != new_dims[player] - 1:
            continue
        source = list(index)
        source[player] = action
        cloned[(slice(None),) + index] = payoffs[(slice(None),) + tuple(source)]

    return cloned


def add_offset(
    payoffs: np.ndarray,
    offsets: np.ndarray,
) -> np.ndarray:
    """
    Add b_p(a_-p) offsets without changing deviation gains.

    offsets[p] should have shape action_dims with player p removed.
    """
    adjusted = payoffs.copy()
    action_dims = payoffs.shape[1:]
    for p in range(payoffs.shape[0]):
        for joint in np.ndindex(*action_dims):
            other_joint = joint[:p] + joint[p + 1 :]
            adjusted[(p,) + joint] += float(offsets[p][other_joint])
    return adjusted
