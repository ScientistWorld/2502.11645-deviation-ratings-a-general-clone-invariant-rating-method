"""
Deviation rating via the sequential LP in Algorithm 1 of the paper.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy.optimize import linprog


def joint_to_flat(joint: List[int], action_dims: List[int]) -> int:
    """Convert a joint action to the flat index used by numpy's C-order storage."""
    flat = 0
    stride = 1
    for action, dim in zip(reversed(joint), reversed(action_dims)):
        flat += action * stride
        stride *= dim
    return flat


def enumerate_joint_actions(action_dims: List[int]) -> np.ndarray:
    """Enumerate joint actions in the same order as numpy.ravel on a C-order array."""
    mesh = np.meshgrid(*[np.arange(dim) for dim in action_dims], indexing="ij")
    return np.stack([axis.reshape(-1) for axis in mesh], axis=1)


@dataclass
class DeviationRatingResult:
    ratings_dict: Dict[int, Dict[int, float]]
    equilibrium: np.ndarray
    n_iterations: int
    active_constraints: List[Tuple[int, int]]
    epsilon_history: List[float]


def _build_deviation_coefficients(
    payoffs: np.ndarray,
    num_players: int,
    action_dims: List[int],
) -> Tuple[np.ndarray, np.ndarray]:
    joint_actions = enumerate_joint_actions(action_dims)
    num_joint = joint_actions.shape[0]
    max_actions = max(action_dims)
    coeff = np.zeros((num_players, max_actions, num_joint), dtype=float)

    for j, joint in enumerate(joint_actions):
        joint_list = joint.tolist()
        flat_orig = joint_to_flat(joint_list, action_dims)
        for p in range(num_players):
            for ap in range(action_dims[p]):
                joint_new = list(joint_list)
                joint_new[p] = ap
                flat_new = joint_to_flat(joint_new, action_dims)
                coeff[p, ap, j] = payoffs[p].reshape(-1)[flat_new] - payoffs[p].reshape(-1)[flat_orig]

    return coeff, joint_actions


def _quantize(arr: np.ndarray, decimals: int = 14) -> np.ndarray:
    """The paper notes that small quantization helps numerical conditioning."""
    return np.round(arr.astype(float), decimals=decimals)


def deviation_rating(
    payoffs: np.ndarray,
    num_players: int,
    action_dims: List[int],
    verbose: bool = False,
    tol: float = 1e-9,
    active_tol: float = 1e-8,
    max_iterations: Optional[int] = None,
    freeze_rule: str = "dual",
    lp_options: Optional[Dict[str, Any]] = None,
    bands: Tuple[float, ...] = (0.0, 1e-9, 1e-8, 1e-7),
) -> Dict[str, Any]:
    """
    Compute deviation ratings by iteratively minimizing the maximum deviation gain.

    The auxiliary variable epsilon is intentionally unbounded below so the solver can
    find strict equilibria with negative deviation gains.

    ``freeze_rule="dual"`` (default) freezes exactly the max constraints with a nonzero
    dual variable, as in Section 4.1 of the paper ("Nonzero dual variables indicate that
    the constraint is active and can be frozen"). By complementary slackness these
    constraints are tight at every optimal distribution, so their ratings are unique.
    ``freeze_rule="active"`` is the earlier implementation's rule, which additionally
    froze every constraint that happened to be tight at the vertex the solver returned;
    when the optimal face is not a single point (e.g. a player whose best action pins
    epsilon at 0) that freezes ratings that later iterations should have lowered, so the
    result depends on the solver's vertex choice. It is kept only for diagnostics.
    ``lp_options`` is passed to SciPy's HiGHS backend.

    Numerics (Appendix B: "care needs to be taken to minimize the accumulation of
    errors"): the deviation coefficients are divided by the payoff scale before
    quantization, so tolerances are relative. Frozen ratings are imposed as
    equalities; only if the solver then reports the LP infeasible (round-off
    accumulated over earlier iterations) is the iteration re-solved with each
    frozen rating held in a band of half-width ``bands[i]`` (relative) around its
    value, and then re-centred on the previous iteration's distribution (feasible
    by construction). In exact arithmetic none of this changes the selection. The returned
    ratings are the deviation gains of the returned distribution, recomputed at
    the end, so they and the equilibrium are always consistent.
    """
    if max_iterations is None:
        max_iterations = sum(action_dims)

    num_joint = int(np.prod(action_dims))
    all_constraints = [(p, ap) for p in range(num_players) for ap in range(action_dims[p])]
    total_constraints = len(all_constraints)
    max_actions = max(action_dims)

    coeff, _ = _build_deviation_coefficients(payoffs, num_players, action_dims)
    scale = max(1.0, float(np.max(np.abs(payoffs))))
    coeff = _quantize(coeff / scale)

    ratings = np.zeros((num_players, max_actions), dtype=float)
    active_constraints: set[Tuple[int, int]] = set()
    epsilon_history: List[float] = []
    sigma_star = np.full(num_joint, 1.0 / num_joint, dtype=float)

    num_solves = 0
    for iteration in range(max_iterations):
        if len(active_constraints) == total_constraints:
            break

        if verbose:
            print(f"iteration={iteration + 1} frozen={len(active_constraints)}/{total_constraints}")

        n_vars = num_joint + 1
        epsilon_idx = num_joint

        A_ub_list = []
        b_ub_list = []
        unfrozen_constraints: List[Tuple[int, int]] = []
        for p, ap in all_constraints:
            if (p, ap) in active_constraints:
                continue
            row = np.zeros(n_vars, dtype=float)
            row[:num_joint] = coeff[p, ap]
            row[epsilon_idx] = -1.0
            A_ub_list.append(row)
            b_ub_list.append(0.0)
            unfrozen_constraints.append((p, ap))

        bounds = [(0.0, None)] * num_joint + [(None, None)]
        objective = np.zeros(n_vars, dtype=float)
        objective[epsilon_idx] = 1.0
        frozen = [(p, ap) for p, ap in all_constraints if (p, ap) in active_constraints]
        simplex_row = np.zeros(n_vars, dtype=float)
        simplex_row[:num_joint] = 1.0

        # Equalities first; on reported infeasibility (accumulated round-off) hold the
        # frozen gains in narrow bands, then re-centre them on the previous
        # iteration's distribution, which satisfies them by construction.
        attempts = [(band, False, None) for band in bands]
        attempts += [(0.0, True, None), (1e-9, True, None), (1e-8, True, {"presolve": False}),
                     (1e-7, True, {"presolve": False})]
        result = None
        for band, recenter, extra in attempts:
            targets = {c: (float(np.dot(coeff[c], sigma_star)) if recenter else float(ratings[c])) for c in frozen}
            rows_ub, rhs_ub = list(A_ub_list), list(b_ub_list)
            rows_eq, rhs_eq = [], []
            for c in frozen:
                row = np.zeros(n_vars, dtype=float)
                row[:num_joint] = coeff[c]
                if band == 0.0:
                    rows_eq.append(row)
                    rhs_eq.append(targets[c])
                else:
                    rows_ub += [row, -row]
                    rhs_ub += [targets[c] + band, -(targets[c] - band)]
            rows_eq.append(simplex_row)
            rhs_eq.append(1.0)
            options = dict(lp_options or {})
            options.update(extra or {})
            result = linprog(
                c=objective,
                A_ub=np.array(rows_ub, dtype=float) if rows_ub else None,
                b_ub=np.array(rhs_ub, dtype=float) if rhs_ub else None,
                A_eq=np.array(rows_eq, dtype=float),
                b_eq=np.array(rhs_eq, dtype=float),
                bounds=bounds,
                method="highs",
                options=options,
            )
            if result.success:
                if recenter:
                    for c in frozen:
                        ratings[c] = targets[c]
                break
        if result is None or not result.success:
            raise RuntimeError(f"LP failed in iteration {iteration + 1}: {result.message}")
        num_solves += 1

        sigma_star = np.maximum(result.x[:num_joint], 0.0)
        sigma_sum = sigma_star.sum()
        if sigma_sum <= 0:
            raise RuntimeError("LP returned a degenerate probability vector")
        sigma_star /= sigma_sum
        epsilon_star = float(result.x[epsilon_idx])
        epsilon_history.append(epsilon_star)

        new_active_set: set[Tuple[int, int]] = set()
        marginals = None
        if result.ineqlin is not None and getattr(result.ineqlin, "marginals", None) is not None:
            marginals = np.asarray(result.ineqlin.marginals, dtype=float).reshape(-1)

        if marginals is not None and marginals.size:
            for idx, marginal in enumerate(marginals[: len(unfrozen_constraints)]):
                if abs(marginal) > active_tol:
                    p, ap = unfrozen_constraints[idx]
                    ratings[p, ap] = float(np.dot(coeff[p, ap], sigma_star))
                    new_active_set.add((p, ap))

        # Paper rule: only the constraints with nonzero duals (frozen above) are
        # tight at every optimum. A tight constraint with a zero dual may still be
        # lowered at another optimal distribution; it is frozen in a later
        # iteration if it is truly pinned. The "active" rule below is diagnostic.
        if freeze_rule == "active":
            for p, ap in unfrozen_constraints:
                delta = float(np.dot(coeff[p, ap], sigma_star))
                if abs(delta - epsilon_star) <= active_tol:
                    ratings[p, ap] = delta
                    new_active_set.add((p, ap))
        elif freeze_rule != "dual":
            raise ValueError(f"Unknown freeze_rule: {freeze_rule}")

        if not new_active_set:
            best = None
            best_delta = -np.inf
            for p, ap in all_constraints:
                if (p, ap) in active_constraints:
                    continue
                delta = float(np.dot(coeff[p, ap], sigma_star))
                if delta > best_delta:
                    best_delta = delta
                    best = (p, ap)
            if best is None:
                raise RuntimeError("No constraint available to freeze")
            ratings[best[0], best[1]] = best_delta
            new_active_set.add(best)

        new_active = sorted(new_active_set)

        for constraint in new_active:
            active_constraints.add(constraint)

        if verbose:
            print(f"  epsilon={epsilon_star:.12f} new_active={new_active}")

    # Report the deviation gains of the returned distribution (payoff units). The
    # frozen values above equal them up to solver round-off.
    ratings_dict = {
        p: {ap: float(np.dot(coeff[p, ap], sigma_star)) * scale for ap in range(action_dims[p])}
        for p in range(num_players)
    }

    return {
        "ratings_dict": ratings_dict,
        "equilibrium": sigma_star,
        "n_iterations": num_solves,
        "active_constraints": sorted(active_constraints),
        "epsilon_history": epsilon_history,
    }


def uniform_rating(
    payoffs: np.ndarray,
    num_players: int,
    action_dims: List[int],
) -> Dict[int, Dict[int, float]]:
    """Rate each action by averaging uniformly over the other players' actions."""
    ratings: Dict[int, Dict[int, float]] = {}
    num_joint = int(np.prod(action_dims))
    joint_actions = enumerate_joint_actions(action_dims)
    flat_payoffs = [payoffs[p].reshape(-1) for p in range(num_players)]

    for p in range(num_players):
        ratings[p] = {}
        for ap in range(action_dims[p]):
            values = []
            for j in range(num_joint):
                joint = joint_actions[j].tolist()
                if joint[p] != ap:
                    continue
                values.append(float(flat_payoffs[p][joint_to_flat(joint, action_dims)]))
            ratings[p][ap] = float(np.mean(values)) if values else 0.0

    return ratings


def cce_gap(
    payoffs: np.ndarray,
    sigma: np.ndarray,
    num_players: int,
    action_dims: List[int],
) -> float:
    """Return the nonnegative CCE regret gap."""
    sigma = np.asarray(sigma, dtype=float).reshape(-1)
    sigma = np.maximum(sigma, 0.0)
    sigma /= sigma.sum()

    coeff, _ = _build_deviation_coefficients(payoffs, num_players, action_dims)
    total_gap = 0.0
    for p in range(num_players):
        deviations = [float(np.dot(coeff[p, ap], sigma)) for ap in range(action_dims[p])]
        total_gap += max(0.0, max(deviations))
    return float(total_gap)


def biased_shapley_game() -> Tuple[np.ndarray, List[str], Dict[str, str]]:
    """Biased Shapley game from Table 2 of the paper."""
    payoffs = np.array(
        [
            [[-8, -2, 4], [2, -8, -1], [-4, 1, -8]],
            [[-8, 2, -4], [-2, -8, 1], [4, -1, -8]],
        ],
        dtype=float,
    )
    return payoffs, ["R", "P", "S"], {"game_name": "biased_shapley"}


def standard_shapley_game() -> Tuple[np.ndarray, List[str], Dict[str, str]]:
    """Standard zero-sum RPS-like Shapley game."""
    payoffs = np.array(
        [
            [[0, -1, 1], [1, 0, -1], [-1, 1, 0]],
            [[0, 1, -1], [-1, 0, 1], [1, -1, 0]],
        ],
        dtype=float,
    )
    return payoffs, ["R", "P", "S"], {"game_name": "standard_shapley"}
