"""
Deviation Rating: N-player general-sum clone-invariant rating based on CCE.

Implements Algorithm 1 from "Deviation Ratings: A General, Clone Invariant Rating Method"
(Marris, Liu, Gemp, Piliouras, Lanctot — Google DeepMind).

Key insight: Select for the strictest CCE (minimizing the maximum deviation gain).
Ratings are the deviation gains at this strictest CCE.
"""

import numpy as np
import cvxpy as cp
from typing import Dict, List, Tuple, Optional, Any


def joint_to_flat(joint: np.ndarray, action_dims: List[int]) -> int:
    """Convert joint action tuple to flat numpy index."""
    flat = 0
    stride = 1
    for q in range(len(action_dims)):
        flat += joint[q] * stride
        stride *= action_dims[q]
    return flat


def deviation_rating(
    payoffs: np.ndarray,
    num_players: int,
    action_dims: List[int],
    solver: str = "SCS",
    verbose: bool = False,
    eps_abs: float = 1e-9,
    eps_rel: float = 1e-9,
    max_iterations: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Compute deviation ratings for all strategies via Algorithm 1.

    Iteratively minimizes the maximum deviation gain, freezing constraints.
    Each iteration solves: min_σ,ε ε s.t. σ ∈ Δ, δ_σ(a'_p) = r_p(a'_p) ∀ frozen,
    and δ_σ(a'_p) ≤ ε ∀ not frozen.
    """
    if max_iterations is None:
        max_iterations = sum(action_dims)

    num_joint = int(np.prod(action_dims))

    # Precompute joint action indices for each player
    joint_actions = np.zeros((num_players, num_joint), dtype=int)
    for p in range(num_players):
        for j in range(num_joint):
            idx = j
            for q in range(p):
                idx //= action_dims[q]
            joint_actions[p, j] = idx % action_dims[p]

    # Precompute flat payoff indices for all joint actions
    flat_indices = np.zeros((num_players, num_joint), dtype=int)
    for p in range(num_players):
        for j in range(num_joint):
            joint = np.array([joint_actions[q, j] for q in range(num_players)])
            flat_indices[p, j] = joint_to_flat(joint, action_dims)

    # List of all (player, action) constraints
    all_constraints = [(p, ap) for p in range(num_players) for ap in range(action_dims[p])]
    total_constraints = len(all_constraints)

    # Precompute deviation gain coefficients
    # coeff[p, ap, j] = payoff if p plays ap vs joint j's opponents - payoff at joint j
    max_actions = max(action_dims)
    coeff = np.zeros((num_players, max_actions, num_joint))
    for (p, ap) in all_constraints:
        for j in range(num_joint):
            joint = np.array([joint_actions[q, j] for q in range(num_players)])
            joint[p] = ap
            flat_new = joint_to_flat(joint, action_dims)
            coeff[p, ap, j] = payoffs[p].flat[flat_new] - payoffs[p].flat[flat_indices[p, j]]

    ratings = np.zeros((num_players, max_actions))
    active_constraints = set()

    for iteration in range(max_iterations):
        if len(active_constraints) >= total_constraints:
            break

        if verbose:
            n_rated = len(active_constraints)
            print(f"  Iter {iteration + 1}: {n_rated}/{total_constraints} rated")

        # LP: minimize ε subject to CCE constraints
        sigma = cp.Variable(num_joint, nonneg=True)
        eps = cp.Variable(nonneg=True)
        objective = cp.Minimize(eps)
        constraints = [cp.sum(sigma) == 1]

        for (p, ap) in all_constraints:
            if (p, ap) in active_constraints:
                # Frozen: deviation gain == stored rating
                delta = coeff[p, ap, :] @ sigma
                constraints.append(delta == ratings[p, ap])
            else:
                # Active: deviation gain <= ε
                delta = coeff[p, ap, :] @ sigma
                constraints.append(delta <= eps)

        prob = cp.Problem(objective, constraints)

        # Solve with fallback
        status = None
        for s in [solver, "SCS", "ECOS", "OSQP"]:
            try:
                if s == "SCS":
                    prob.solve(solver=s, verbose=False, eps_abs=eps_abs, eps_rel=eps_rel,
                               max_iters=10000, acceleration_lookback=0)
                elif s == "ECOS":
                    prob.solve(solver=s, verbose=False, abstol=eps_abs, reltol=eps_rel,
                               feastol=eps_abs, maxit=10000)
                elif s == "OSQP":
                    prob.solve(solver=s, verbose=False, eps_abs=eps_abs, eps_rel=eps_rel,
                               max_iter=10000)
                else:
                    prob.solve(solver=s, verbose=False)
                status = prob.status
                break
            except (cp.SolverError, Exception) as e:
                if verbose:
                    print(f"    Solver {s} failed: {e}")
                continue

        if status not in ["optimal", "optimal_inaccurate"]:
            if verbose:
                print(f"    Status: {status}, value: {prob.value}")
            if sigma.value is None:
                sigma_val = np.ones(num_joint) / num_joint
                eps_val = 0.0
            else:
                sigma_val = np.maximum(np.array(sigma.value).flatten(), 0)
                sigma_val /= sigma_val.sum()
                eps_val = float(eps.value) if eps.value is not None else 0.0
        else:
            sigma_val = np.maximum(np.array(sigma.value).flatten(), 0)
            sigma_val /= sigma_val.sum()
            eps_val = float(eps.value) if eps.value is not None else 0.0

        # Identify newly active constraints
        new_active = []
        for (p, ap) in all_constraints:
            if (p, ap) in active_constraints:
                continue
            delta_val = float(np.dot(coeff[p, ap, :], sigma_val))
            if abs(delta_val - eps_val) < 1e-4:
                new_active.append((p, ap))
                ratings[p, ap] = delta_val

        # Force-freeze at least one if none found
        if len(new_active) == 0:
            best = None
            best_val = -1e20
            for (p, ap) in all_constraints:
                if (p, ap) in active_constraints:
                    continue
                dv = float(np.dot(coeff[p, ap, :], sigma_val))
                if dv > best_val:
                    best_val = dv
                    best = (p, ap)
            if best is not None:
                new_active.append(best)
                ratings[best[0], best[1]] = best_val

        for pa in new_active:
            active_constraints.add(pa)
            if verbose:
                print(f"    Froze {pa}: r={ratings[pa[0], pa[1]]:.6f}")

    ratings_dict = {
        p: {ap: float(ratings[p, ap]) for ap in range(action_dims[p])}
        for p in range(num_players)
    }

    return {
        "ratings_dict": ratings_dict,
        "equilibrium": sigma_val,
        "n_iterations": iteration + 1,
    }


def uniform_rating(
    payoffs: np.ndarray,
    num_players: int,
    action_dims: List[int],
) -> Dict[int, Dict[int, float]]:
    """
    Compute uniform average ratings.
    r_p(a'_p) = (1/|A_{-p}|) * Σ_{a_{-p}} G_p(a'_p, a_{-p})
    """
    ratings = {}
    num_joint = int(np.prod(action_dims))
    for p in range(num_players):
        ratings[p] = {}
        for ap in range(action_dims[p]):
            total = 0.0
            count = 0
            for j in range(num_joint):
                joint = [0] * num_players
                idx = j
                for q in range(num_players):
                    joint[q] = idx % action_dims[q]
                    idx //= action_dims[q]
                if joint[p] == ap:
                    total += payoffs[p].item(tuple(joint))
                    count += 1
            ratings[p][ap] = total / count if count > 0 else 0.0
    return ratings


def cce_gap(
    payoffs: np.ndarray,
    sigma: np.ndarray,
    num_players: int,
    action_dims: List[int],
) -> float:
    """
    Compute CCE gap: sum_p max_{a'_p} δ_p(a'_p)
    """
    if sigma is None:
        return float('inf')

    num_joint = int(np.prod(action_dims))
    sigma = np.array(sigma).flatten()
    sigma = np.maximum(sigma, 0)
    sigma /= sigma.sum()

    joint_actions = np.zeros((num_players, num_joint), dtype=int)
    for p in range(num_players):
        for j in range(num_joint):
            idx = j
            for q in range(p):
                idx //= action_dims[q]
            joint_actions[p, j] = idx % action_dims[p]

    total_gap = 0.0
    for p in range(num_players):
        max_dev = -1e20
        for ap in range(action_dims[p]):
            delta = 0.0
            for j in range(num_joint):
                joint = np.array([joint_actions[q, j] for q in range(num_players)])
                joint_p = joint.copy()
                joint_p[p] = ap
                flat_orig = joint_to_flat(joint, action_dims)
                flat_new = joint_to_flat(joint_p, action_dims)
                delta += sigma[j] * (payoffs[p].flat[flat_new] - payoffs[p].flat[flat_orig])
            if delta > max_dev:
                max_dev = delta
        total_gap += max_dev

    return float(total_gap)


def biased_shapley_game() -> Tuple[np.ndarray, List[str], Dict]:
    """
    The biased Shapley game from the paper.
    2-player game with R, P, S forming a cycle and same-action penalty.
    Payoffs from the cycle: R beats S (+4), S beats P (+1), P beats R (+2).
    Same action: both get -8.
    """
    R, P, S = 0, 1, 2

    payoffs = np.array([
        # P0's payoff vs P1's action
        [[-8,  2,  4],   # P0=R: vs R=-8, P=+2, S=+4
         [-2, -8, -1],    # P0=P: vs R=-2, P=-8, S=-1
         [-4,  1, -8]],   # P0=S: vs R=-4, P=+1, S=-8
        # P1's payoff (negative of P0's)
        [[-8, -2, -4],
         [ 2, -8,  1],
         [ 4, -1, -8]],
    ])

    return payoffs, ["R", "P", "S"], {"game_name": "biased_shapley"}


def standard_shapley_game() -> Tuple[np.ndarray, List[str], Dict]:
    """
    Standard (unbiased) Shapley game: R beats S (+1), S beats P (+1), P beats R (+1), same=0.
    """
    payoffs = np.array([
        [[0, -1, 1],
         [1, 0, -1],
         [-1, 1, 0]],
        [[0, 1, -1],
         [-1, 0, 1],
         [1, -1, 0]],
    ])
    return payoffs, ["R", "P", "S"], {"game_name": "standard_shapley"}
