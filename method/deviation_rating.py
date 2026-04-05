"""
Deviation Rating: N-player general-sum clone-invariant rating based on CCE.

Implements Algorithm 1 from "Deviation Ratings: A General, Clone Invariant Rating Method"
(Marris, Liu, Gemp, Piliouras, Lanctot — Google DeepMind).

Key insight: Find the strictest CCE (minimizing max deviation gain ε).
Ratings are the deviation gains at this equilibrium.
"""

import numpy as np
from scipy.optimize import linprog
from typing import Dict, List, Tuple, Optional


def joint_to_flat(joint: List[int], action_dims: List[int]) -> int:
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
    verbose: bool = False,
    tol: float = 1e-9,
    max_iterations: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Compute deviation ratings via Algorithm 1 (CCE-based sequential LP).

    The LP in each iteration:
        min ε
        s.t.  Σ_j σ[j] * coeff[p,ap,j] ≤ ε   for all (p,ap) not frozen
              Σ_j σ[j] * coeff[p,ap,j] = r_p(ap)   for all (p,ap) frozen
              Σ_j σ[j] = 1,  σ[j] ≥ 0
    """
    if max_iterations is None:
        max_iterations = sum(action_dims)

    num_joint = int(np.prod(action_dims))

    # Precompute joint action indices
    joint_actions = np.zeros((num_players, num_joint), dtype=int)
    for p in range(num_players):
        for j in range(num_joint):
            idx = j
            for q in range(p):
                idx //= action_dims[q]
            joint_actions[p, j] = idx % action_dims[p]

    # Precompute flat indices for original joint actions
    flat_indices = np.zeros((num_players, num_joint), dtype=int)
    for p in range(num_players):
        for j in range(num_joint):
            joint = [int(joint_actions[q, j]) for q in range(num_players)]
            flat_indices[p, j] = joint_to_flat(joint, action_dims)

    # Precompute deviation gain coefficients
    # coeff[p, ap, j] = G_p(ap, a_{-p}(j)) - G_p(a(j))
    all_constraints = [(p, ap) for p in range(num_players) for ap in range(action_dims[p])]
    total_constraints = len(all_constraints)
    max_actions = max(action_dims)
    coeff = np.zeros((num_players, max_actions, num_joint))

    for (p, ap) in all_constraints:
        for j in range(num_joint):
            joint_new = [int(joint_actions[q, j]) for q in range(num_players)]
            joint_new[p] = ap
            flat_new = joint_to_flat(joint_new, action_dims)
            coeff[p, ap, j] = payoffs[p].flat[flat_new] - payoffs[p].flat[flat_indices[p, j]]

    ratings = np.zeros((num_players, max_actions))
    active_constraints = set()
    sigma_star = np.ones(num_joint) / num_joint

    for iteration in range(max_iterations):
        if len(active_constraints) >= total_constraints:
            break

        if verbose:
            print(f"  Iter {iteration + 1}: {len(active_constraints)}/{total_constraints} frozen")

        # Build LP: min ε s.t. A_ub @ [σ; ε] ≤ b_ub, A_eq @ [σ; ε] = b_eq
        # Variables: first num_joint are σ[j], last 1 is ε
        n_vars = num_joint + 1

        # Inequality constraints: coeff[p,ap,:] @ σ - ε ≤ 0 (for non-frozen)
        # and coeff[p,ap,:] @ σ - ε ≤ 0 means deviation ≤ ε
        A_ub_list = []
        b_ub_list = []
        for (p, ap) in all_constraints:
            if (p, ap) not in active_constraints:
                row = np.zeros(n_vars)
                row[:num_joint] = coeff[p, ap, :]
                row[num_joint] = -1.0  # -ε
                A_ub_list.append(row)
                b_ub_list.append(0.0)

        A_ub = np.array(A_ub_list) if A_ub_list else np.zeros((0, n_vars))
        b_ub = np.array(b_ub_list) if b_ub_list else np.zeros(0)

        # Equality constraints: coeff[p,ap,:] @ σ = r_p(ap) for frozen
        A_eq_list = []
        b_eq_list = []
        for (p, ap) in all_constraints:
            if (p, ap) in active_constraints:
                row = np.zeros(n_vars)
                row[:num_joint] = coeff[p, ap, :]
                A_eq_list.append(row)
                b_eq_list.append(ratings[p, ap])

        # Simplex: Σ_j σ[j] = 1
        simplex_row = np.zeros(n_vars)
        simplex_row[:num_joint] = 1.0
        A_eq_list.append(simplex_row)
        b_eq_list.append(1.0)

        A_eq = np.array(A_eq_list) if A_eq_list else np.zeros((0, n_vars))
        b_eq = np.array(b_eq_list) if b_eq_list else np.zeros(0)

        # Bounds: σ[j] ≥ 0, ε ≥ 0
        bounds = [(0, None)] * num_joint + [(0, None)]

        # Objective: minimize ε (last variable)
        c = np.zeros(n_vars)
        c[num_joint] = 1.0

        result = linprog(
            c, A_ub=A_ub, b_ub=b_ub,
            A_eq=A_eq, b_eq=b_eq,
            bounds=bounds,
            method='highs',
            options={'tol': tol, 'maxiter': 10000, 'disp': False}
        )

        if result.success or result.status in [0, 2]:  # 0=optimal, 2=optimal_inaccurate
            sigma_star = np.maximum(result.x[:num_joint], 0)
            sigma_star /= sigma_star.sum()
            eps_star = result.x[num_joint]
        else:
            if verbose:
                print(f"    LP failed: {result.message}, status={result.status}")
            # Keep previous sigma

        # Identify newly active constraints
        new_active = []
        for (p, ap) in all_constraints:
            if (p, ap) in active_constraints:
                continue
            delta = np.dot(coeff[p, ap, :], sigma_star)
            if abs(delta - eps_star) < 1e-4:
                new_active.append((p, ap))
                ratings[p, ap] = delta

        # Force freeze at least one if needed
        if len(new_active) == 0:
            best = None
            best_val = -1e20
            for (p, ap) in all_constraints:
                if (p, ap) in active_constraints:
                    continue
                dv = np.dot(coeff[p, ap, :], sigma_star)
                if dv > best_val:
                    best_val = dv
                    best = (p, ap)
            if best is not None:
                new_active.append(best)
                ratings[best[0], best[1]] = best_val

        for pa in new_active:
            active_constraints.add(pa)
            if verbose:
                print(f"    Froze {pa}: r={ratings[pa[0], pa[1]]:.8f}")

    ratings_dict = {
        p: {ap: float(ratings[p, ap]) for ap in range(action_dims[p])}
        for p in range(num_players)
    }

    return {
        "ratings_dict": ratings_dict,
        "equilibrium": sigma_star,
        "n_iterations": iteration + 1,
        "active_constraints": active_constraints,
    }


def uniform_rating(
    payoffs: np.ndarray,
    num_players: int,
    action_dims: List[int],
) -> Dict[int, Dict[int, float]]:
    """Compute uniform average ratings."""
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
    """Compute CCE gap: sum_p max_{a'_p} δ_p(a'_p)."""
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
                joint = [int(joint_actions[q, j]) for q in range(num_players)]
                joint_new = list(joint)
                joint_new[p] = ap
                flat_orig = joint_to_flat(joint, action_dims)
                flat_new = joint_to_flat(joint_new, action_dims)
                delta += sigma[j] * (payoffs[p].flat[flat_new] - payoffs[p].flat[flat_orig])
            if delta > max_dev:
                max_dev = delta
        total_gap += max_dev

    return float(total_gap)


def biased_shapley_game() -> Tuple[np.ndarray, List[str], Dict]:
    """
    Biased Shapley game: 2-player 3x3.
    R beats S (+4), S beats P (+1), P beats R (+2), same=(-8).
    """
    # payoffs[p, a1, a2] = payoff to player p
    payoffs = np.array([
        # P0 payoff
        [[-8,  2,  4],
         [-2, -8, -1],
         [-4,  1, -8]],
        # P1 payoff (zero-sum: negative of P0)
        [[-8, -2, -4],
         [ 2, -8,  1],
         [ 4, -1, -8]],
    ])
    return payoffs, ["R", "P", "S"], {"game_name": "biased_shapley"}


def standard_shapley_game() -> Tuple[np.ndarray, List[str], Dict]:
    """Standard Shapley game: +1/-1/0 payoffs."""
    payoffs = np.array([
        [[0, -1, 1], [1, 0, -1], [-1, 1, 0]],
        [[0, 1, -1], [-1, 0, 1], [1, -1, 0]],
    ])
    return payoffs, ["R", "P", "S"], {"game_name": "standard_shapley"}
