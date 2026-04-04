"""
Deviation Rating: N-player general-sum clone-invariant rating based on Coarse Correlated Equilibrium (CCE).

Implements Algorithm 1 from "Deviation Ratings: A General, Clone Invariant Rating Method"
(Marris, Liu, Gemp, Piliouras, Lanctot — Google DeepMind).

The algorithm computes unique deviation ratings for strategies in any N-player normal-form game
by iteratively solving linear programs that find the strictest CCE (minimizing max deviation gains).
"""

import numpy as np
import cvxpy as cp
from typing import Dict, List, Tuple, Optional, Any


def joint_to_flat(joint: np.ndarray, action_dims: List[int]) -> int:
    """Convert a joint action tuple to flat index."""
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
    solver: str = "ECOS",
    verbose: bool = False,
    quantization: float = 1e-10,
    max_iterations: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Compute deviation ratings for all strategies of all players.

    Parameters
    ----------
    payoffs : np.ndarray
        Shape (num_players, *action_dims) — payoffs[p, a1, ..., aN] = payoff to player p
    num_players : int
        Number of players N
    action_dims : List[int]
        Number of actions for each player
    solver : str
        LP solver to use (ECOS, GLOP, SCS, etc.)
    verbose : bool
        Whether to print debug info
    quantization : float
        Quantize payoffs to this precision for numerical stability
    max_iterations : Optional[int]
        Maximum outer iterations (defaults to sum(action_dims))

    Returns
    -------
    Dict with keys:
        'ratings_dict': Dict mapping player -> action_index -> rating
        'equilibrium': the final CCE distribution sigma
        'n_iterations': number of outer iterations
    """
    if max_iterations is None:
        max_iterations = sum(action_dims)

    # Quantize payoffs for numerical stability
    payoffs = np.round(payoffs / quantization) * quantization

    # Total number of joint actions
    num_joint = int(np.prod(action_dims))

    # Precompute joint action mappings
    # joint_actions[p, j] = action index for player p in joint j
    joint_actions = np.zeros((num_players, num_joint), dtype=int)
    for p in range(num_players):
        for j in range(num_joint):
            idx = j
            for q in range(p):
                idx //= action_dims[q]
            joint_actions[p, j] = idx % action_dims[p]

    # Precompute flat indices for all joints
    flat_indices = np.zeros((num_players, num_joint), dtype=int)
    for p in range(num_players):
        for j in range(num_joint):
            joint = [joint_actions[q, j] for q in range(num_players)]
            flat_indices[p, j] = joint_to_flat(np.array(joint), action_dims)

    # Precompute deviation gain coefficients for each (p, a'_p) constraint
    # coeff[p, ap, j] = G_p(ap, a_{-p}(j)) - G_p(a(j))
    all_constraints = []
    for p in range(num_players):
        for ap in range(action_dims[p]):
            all_constraints.append((p, ap))

    coeff = np.zeros((num_players, max(action_dims), num_joint))
    for (p, ap) in all_constraints:
        for j in range(num_joint):
            # Joint where p plays ap, others play their joint actions
            joint_new = [joint_actions[q, j] for q in range(num_players)]
            joint_new[p] = ap
            flat_new = joint_to_flat(np.array(joint_new), action_dims)
            coeff[p, ap, j] = payoffs[p].flat[flat_new] - payoffs[p].flat[flat_indices[p, j]]

    total_constraints = len(all_constraints)
    ratings = np.zeros((num_players, max(action_dims)))
    active_constraints = set()
    n_iterations = 0

    for iteration in range(max_iterations):
        n_iterations += 1

        # Check if all constraints are frozen
        if len(active_constraints) >= total_constraints:
            break

        if verbose:
            n_rated = sum(1 for (p, ap) in all_constraints if (p, ap) in active_constraints)
            print(f"  Iteration {iteration + 1}: {n_rated}/{total_constraints} rated")

        # LP variables
        sigma = cp.Variable(num_joint, nonneg=True)
        eps = cp.Variable(nonneg=True)

        # Objective: minimize max deviation gain
        objective = cp.Minimize(eps)

        # Constraints
        constraints = [cp.sum(sigma) == 1]  # simplex

        for (p, ap) in all_constraints:
            if (p, ap) in active_constraints:
                # Frozen: deviation gain == stored rating
                delta = cp.sum(cp.multiply(coeff[p, ap, :], sigma))
                constraints.append(delta == ratings[p, ap])
            else:
                # Active: deviation gain <= eps
                delta = cp.sum(cp.multiply(coeff[p, ap, :], sigma))
                constraints.append(delta <= eps)

        prob = cp.Problem(objective, constraints)

        # Solve with fallback chain
        status = None
        for s in [solver, "ECOS", "SCS", "OSQP"]:
            try:
                prob.solve(solver=s, verbose=False)
                status = prob.status
                break
            except (cp.SolverError, Exception):
                continue

        if status not in ["optimal", "optimal_inaccurate"]:
            if verbose:
                print(f"    Solver status: {status}, value: {prob.value}")
            # Try to continue with whatever we got
            if sigma.value is None:
                # Last resort: uniform distribution
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
            # Compute actual deviation gain at solution
            delta_val = float(np.dot(coeff[p, ap, :], sigma_val))
            # A constraint is active if delta_val is close to eps_val
            if abs(delta_val - eps_val) < 1e-6:
                new_active.append((p, ap))
                ratings[p, ap] = delta_val

        # Force-freeze at least one constraint if none found (due to numerical issues)
        if len(new_active) == 0:
            max_delta = -1e20
            max_pa = None
            for (p, ap) in all_constraints:
                if (p, ap) in active_constraints:
                    continue
                delta_val = float(np.dot(coeff[p, ap, :], sigma_val))
                if delta_val > max_delta:
                    max_delta = delta_val
                    max_pa = (p, ap)
            if max_pa is not None:
                new_active.append(max_pa)
                ratings[max_pa[0], max_pa[1]] = max_delta

        # Add new constraints
        for pa in new_active:
            active_constraints.add(pa)
            if verbose:
                print(f"    Froze {pa}: rating={ratings[pa[0], pa[1]]:.6f}")

    # Build output
    ratings_dict = {
        p: {ap: float(ratings[p, ap]) for ap in range(action_dims[p])}
        for p in range(num_players)
    }

    return {
        "ratings_dict": ratings_dict,
        "equilibrium": sigma_val,
        "n_iterations": n_iterations,
        "active_constraints": active_constraints,
    }


def uniform_rating(
    payoffs: np.ndarray,
    num_players: int,
    action_dims: List[int],
) -> Dict[int, Dict[int, float]]:
    """
    Compute uniform average ratings: mean payoff over all opponents.
    r_p(a'_p) = (1 / |A_{-p}|) * sum_{a_{-p}} G_p(a'_p, a_{-p})
    """
    ratings = {}
    for p in range(num_players):
        ratings[p] = {}
        for ap in range(action_dims[p]):
            total = 0.0
            count = 0
            num_joint = int(np.prod(action_dims))
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
    Compute the CCE gap: sum_p max_{a'_p} delta_p(a'_p)
    """
    if sigma is None:
        return float('inf')

    num_joint = int(np.prod(action_dims))
    sigma = np.array(sigma).flatten()
    sigma = np.maximum(sigma, 0)
    sigma /= sigma.sum()

    # Precompute joint action mappings
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
                joint_new = joint.copy()
                joint_new[p] = ap
                flat_orig = joint_to_flat(joint, action_dims)
                flat_new = joint_to_flat(joint_new, action_dims)
                delta += sigma[j] * (payoffs[p].flat[flat_new] - payoffs[p].flat[flat_orig])
            if delta > max_dev:
                max_dev = delta
        total_gap += max_dev

    return float(total_gap)


def biased_shapley_game() -> Tuple[np.ndarray, List[str], Dict]:
    """Create the biased Shapley game from the paper (Table 2a)."""
    R, P, S, N = 0, 1, 2, 3
    game_payoffs = {
        (R, R): (-8, -8),
        (R, P): (-2, 2),
        (R, S): (4, -4),
        (R, N): (-680/241, -712/241),
        (P, R): (2, -2),
        (P, P): (-8, -8),
        (P, S): (-1, 1),
        (P, N): (-680/241, -920/241),
        (S, R): (-4, 4),
        (S, P): (1, -1),
        (S, S): (-8, -8),
        (S, N): (-680/241, -184/241),
        (N, R): (-712/241, -680/241),
        (N, P): (-920/241, -680/241),
        (N, S): (-184/241, -680/241),
        (N, N): (-680/241, -680/241),
    }

    payoffs = np.zeros((2, 4, 4))
    for (a1, a2), (g1, g2) in game_payoffs.items():
        payoffs[0, a1, a2] = g1
        payoffs[1, a1, a2] = g2

    return payoffs, ["R", "P", "S", "N"], {"game_name": "biased_shapley"}
