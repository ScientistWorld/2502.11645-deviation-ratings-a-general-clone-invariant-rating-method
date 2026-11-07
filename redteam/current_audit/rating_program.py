"""Candidate implementations using only the public interface and improve-mode method.

This file is installed into method/ before evaluation. It never reads eval/test,
score files, evaluator state, hidden seeds, or hidden answers. Shortcut names
are explicit; genuine algorithm variants are separate modes.
"""
from __future__ import annotations

import hashlib
import json
import random
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import linprog


def coefficients(payoffs, num_players, action_dims):
    """Exact vectorized replacement for the reference's Python cell loop."""
    size = int(np.prod(action_dims))
    index = np.arange(size)
    joints = np.stack(np.unravel_index(index, action_dims), axis=1)
    coeff = np.zeros((num_players, max(action_dims), size))
    for p, d in enumerate(action_dims):
        stride = int(np.prod(action_dims[p + 1:]))
        own = joints[:, p]
        target = index[None, :] + (np.arange(d)[:, None] - own[None, :]) * stride
        flat = payoffs[p].reshape(-1)
        coeff[p, :d] = flat[target] - flat[None, :]
    return coeff, joints


def output(payoffs, sigma):
    dims = list(payoffs.shape[1:])
    sigma = np.asarray(sigma, dtype=float).reshape(-1)
    coeff, _ = coefficients(payoffs, len(dims), dims)
    return {"ratings": [(coeff[p, :d] @ sigma).tolist() for p, d in enumerate(dims)],
            "equilibrium": sigma.tolist()}


def reference(payoffs, mode="reference"):
    import method.deviation_rating as module
    options = {}
    if mode in ("vectorized_solver", "precision_solver"):
        module._build_deviation_coefficients = coefficients
    if mode == "precision_solver":
        options = {"active_tol": 1e-10,
                   "lp_options": {"primal_feasibility_tolerance": 1e-10,
                                  "dual_feasibility_tolerance": 1e-10}}
    if mode == "weaker_one_lp":
        options = {"max_iterations": 1}
    if mode == "two_lp_shortcut":
        options = {"max_iterations": 2}
    if mode == "three_lp_shortcut":
        options = {"max_iterations": 3}
    dims = list(payoffs.shape[1:])
    result = module.deviation_rating(payoffs, len(dims), dims, **options)
    return output(payoffs, result["equilibrium"])


def fingerprint(payoffs):
    return hashlib.sha256(json.dumps(payoffs, separators=(",", ":")).encode()).hexdigest()


def lexicographic_lax_shortcut(payoffs):
    """Deliberately reverse the reference's preference for equilibrium strictness."""
    dims = list(payoffs.shape[1:])
    coeff, _ = coefficients(payoffs, len(dims), dims)
    D = np.concatenate([coeff[p, :d] for p, d in enumerate(dims)])
    k, m = D.shape
    frozen = {}
    while len(frozen) < k:
        todo = [i for i in range(k) if i not in frozen]
        res = linprog(np.r_[np.zeros(m), -1.],
                      A_ub=np.r_[np.c_[D, np.zeros(k)], np.c_[-D[todo], np.ones(len(todo))]],
                      b_ub=np.zeros(k + len(todo)),
                      A_eq=[np.r_[np.ones(m), 0.]] + [np.r_[D[i], 0.] for i in frozen],
                      b_eq=[1.] + list(frozen.values()),
                      bounds=[(0, None)] * m + [(None, None)], method="highs")
        if not res.success:
            raise RuntimeError(res.message)
        chosen = [i for j, i in enumerate(todo) if abs(res.ineqlin.marginals[k + j]) > 1e-8]
        if not chosen:
            raise RuntimeError("lax shortcut had no nonzero dual")
        for i in chosen:
            frozen[i] = float(D[i] @ res.x[:m])
    return output(payoffs, res.x[:m])


def candidate(payoffs, mode, cache=None):
    dims = list(payoffs.shape[1:])
    size = int(np.prod(dims))
    if mode == "size_abandonment_shortcut":
        if size > 2048:
            return {"ratings": [[0.] * d for d in dims], "equilibrium": []}
        return reference(payoffs)
    if mode in ("lax_selection_shortcut", "population_lax_shortcut"):
        if mode == "lax_selection_shortcut" or payoffs.shape == (2, 8, 8):
            return lexicographic_lax_shortcut(payoffs)
        return reference(payoffs)
    if mode == "visible_answers_shortcut":
        found = cache.get(fingerprint(payoffs.tolist()))
        if found is not None:
            return found
    if mode in ("reference", "vectorized_solver", "precision_solver", "weaker_one_lp",
                "two_lp_shortcut", "three_lp_shortcut"):
        return reference(payoffs, mode)
    uniform = np.full(size, 1. / size)
    out = output(payoffs, uniform)
    if mode == "constant_ratings_shortcut":
        out["ratings"] = [[0.] * d for d in dims]
    elif mode == "copy_input_shortcut":
        out["ratings"] = [payoffs[p].reshape(-1)[:d].tolist() for p, d in enumerate(dims)]
    elif mode == "empty_output_shortcut":
        return {}
    elif mode == "nonfinite_shortcut":
        out["ratings"][0][0] = float("nan")
        out["equilibrium"][0] = float("inf")
    elif mode == "negative_distribution_shortcut":
        out["equilibrium"] = [-1e100] * size
    elif mode == "reported_fields_shortcut":
        out.update(success=True, CCE_gap=0., strictness_gap=0., seconds=0.,
                   min_margin=1e100, test_size=0, tolerance=1e100,
                   dominance_pairs=[], baseline_score=1e100, ground_truth=[], flags=None)
    return out


def main():
    mode, source, dest = sys.argv[1:]
    seed = 0
    if mode.startswith("reference_seed_"):
        seed = int(mode.rsplit("_", 1)[-1])
        mode = "reference"
    random.seed(seed)
    np.random.seed(seed)
    cache = {}
    if mode == "visible_answers_shortcut":
        cache = json.loads(Path(__file__).with_name("visible_shortcut_cache.json").read_text())
    entries = json.loads(Path(source).read_text())["games"]
    results = {}
    for entry in entries:
        array = np.asarray(entry["payoffs"], dtype=float)
        if mode == "reference" and seed:
            # Relabel actions to stress solver-vertex sensitivity without changing
            # the mathematical reference, its games, or any evaluator seed.
            digest = int(hashlib.sha256(entry["id"].encode()).hexdigest()[:12], 16)
            rng = np.random.default_rng(seed + digest)
            perms = [rng.permutation(d) for d in array.shape[1:]]
            transformed = array
            for p, perm in enumerate(perms):
                transformed = np.take(transformed, perm, axis=p + 1)
            out = reference(transformed)
            sigma = np.asarray(out["equilibrium"]).reshape(array.shape[1:])
            for p, perm in enumerate(perms):
                sigma = np.take(sigma, np.argsort(perm), axis=p)
            out = output(array, sigma)
        else:
            out = candidate(array, mode, cache)
        results[entry["id"]] = out
    Path(dest).write_text(json.dumps({"results": results}))


if __name__ == "__main__":
    main()
