#!/usr/bin/env python3
"""Diagnostics for the population-improvement experiment (paper Section 5.3).

Runs the hidden test's improvement loop (eval/test/evaluate.py: same game,
candidate streams, presentation, gates, tie-breaking and gap measurement) with
in-process rating rules, on pools drawn from a NON-hidden seed:

* reference: method.rate.rate_game through the exact gate + invariance path of
  the test (``_rate_with_program``);
* uniform_payoff, random_selection: the evaluator's baselines;
* alternative CCE selection rules (feasibility CCE, the first LP of Algorithm 1
  only, maximum-welfare CCE, maximum-entropy CCE gains, the earlier
  freeze-every-tight-constraint rule). They are scored without the invariance
  gate so their gap can be seen; their invariance violation is reported.

Usage: python3 redteam/population_diagnostics.py [--runs R] [--iterations T] [--alt-runs R2]
Writes redteam/population_diagnostics.json.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import linprog

ROOT = Path("/home/user")
sys.path.insert(0, str(ROOT))

from method.deviation_rating import deviation_rating  # noqa: E402
from method.rate import rate_game  # noqa: E402

spec = importlib.util.spec_from_file_location("hidden_eval", ROOT / "eval/test/evaluate.py")
H = importlib.util.module_from_spec(spec)
spec.loader.exec_module(H)

DIAG_SEED = 424_242


def as_array(game) -> np.ndarray:
    return np.asarray(game.payload(), dtype=float)


def coeff_matrix(game) -> np.ndarray:
    return np.asarray(H._cce_rows(game), dtype=float)


def lp_sigma(game, objective: str) -> list:
    rows = coeff_matrix(game)
    k, m = rows.shape
    if objective == "single_lp":
        c = np.zeros(m + 1)
        c[-1] = 1.0
        a_ub = np.hstack([rows, -np.ones((k, 1))])
        a_eq = np.hstack([np.ones((1, m)), np.zeros((1, 1))])
        bounds = [(0, None)] * m + [(None, None)]
    else:
        if objective == "feasibility":
            c = np.zeros(m)
        elif objective == "max_welfare":
            c = -np.sum(np.asarray(game.tables, dtype=float), axis=0)
        else:
            raise ValueError(objective)
        a_ub, a_eq, bounds = rows, np.ones((1, m)), [(0, None)] * m
    res = linprog(c, A_ub=a_ub, b_ub=np.zeros(k), A_eq=a_eq, b_eq=[1.0], bounds=bounds, method="highs")
    if not res.success:
        raise RuntimeError(res.message)
    sigma = np.maximum(res.x[:m], 0.0)
    return list(sigma / sigma.sum())


def alt_ratings(game, rule: str):
    if rule == "variant:active":
        arr = as_array(game)
        res = deviation_rating(arr, game.n, list(game.dims), freeze_rule="active")
        return [[float(res["ratings_dict"][p][a]) for a in range(game.dims[p])] for p in range(game.n)]
    if rule == "mecce_gains":
        sigma = H.max_entropy_cce(game, eps_rel=1e-7)
    else:
        sigma = lp_sigma(game, rule)
    return H.deviation_gains(game, sigma)


def make_alt_rate(rule: str, stats: dict):
    def rate(batch):
        out, worst = [], 0.0
        for inst in batch:
            start = time.perf_counter()
            original = alt_ratings(inst["game"], rule)
            stats["seconds"] += time.perf_counter() - start
            stats["games"] += 1
            variant = alt_ratings(inst["variant"], rule)
            worst = max(worst, H._invariance_violation(inst, original, variant))
            out.append(original)
        return out, worst

    return rate


def make_reference_rate(seed: int, stats: dict):
    def call(games, order):
        results = {}
        for gid in order:
            start = time.perf_counter()
            results[gid] = rate_game(games[gid].payload())
            stats["seconds"] += time.perf_counter() - start
            stats["games"] += 1
            check = H.validate_result(games[gid], results[gid])
            stats["max_mismatch"] = max(stats["max_mismatch"], check.get("mismatch", 0.0))
            stats["max_gain"] = max(stats["max_gain"], check.get("max_gain", -math.inf))
        return results, ""

    return H._rate_with_program(call, seed)


def run_rule(name, rate, pools, sheriff, seed):
    start = time.perf_counter()
    try:
        curves, violation = H.population_loop(sheriff, pools, seed, rate)
    except H.PopulationFailure as failure:
        return {"failure": str(failure), "seconds": round(time.perf_counter() - start, 1)}
    metrics = H.population_metrics(curves, violation)
    return {
        "metrics": {k: round(v, 6) for k, v in metrics.items()},
        "curves": [[round(v, 4) for v in c] for c in curves],
        "seconds": round(time.perf_counter() - start, 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=16)
    parser.add_argument("--iterations", type=int, default=256)
    parser.add_argument("--alt-runs", type=int, default=8)
    parser.add_argument("--alt-iterations", type=int, default=128)
    parser.add_argument("--out", default=str(ROOT / "redteam/population_diagnostics.json"))
    args = parser.parse_args()
    report = {"seed": DIAG_SEED, "pop_size": H.POP_SIZE, "drop": H.POP_DROP,
              "checkpoint_every": H.POP_CHECKPOINT_EVERY, "rules": {}}

    def save():
        Path(args.out).write_text(json.dumps(report, indent=1))

    H.POP_ITERATIONS = args.iterations
    sheriff, pools = H.make_pools(DIAG_SEED, runs=args.runs)
    report["long"] = {"runs": args.runs, "iterations": args.iterations}
    for name, rate in (("uniform_payoff", H._rate_uniform), ("random_selection", H._rate_random)):
        report["rules"][name] = run_rule(name, rate, pools, sheriff, DIAG_SEED)
        print(name, report["rules"][name].get("metrics"), report["rules"][name]["seconds"], flush=True)
        save()
    stats = {"seconds": 0.0, "games": 0, "max_mismatch": 0.0, "max_gain": -math.inf}
    report["rules"]["reference"] = run_rule("reference", make_reference_rate(DIAG_SEED, stats), pools, sheriff, DIAG_SEED)
    report["rules"]["reference"]["rating_stats"] = dict(stats, seconds_per_game=stats["seconds"] / max(1, stats["games"]))
    print("reference", report["rules"]["reference"].get("metrics"), report["rules"]["reference"].get("failure"),
          report["rules"]["reference"]["seconds"], stats, flush=True)
    save()

    H.POP_ITERATIONS = args.alt_iterations
    short_pools = pools[: args.alt_runs]
    report["short"] = {"runs": args.alt_runs, "iterations": args.alt_iterations}
    for name in ("feasibility", "single_lp", "max_welfare", "mecce_gains", "variant:active"):
        stats = {"seconds": 0.0, "games": 0}
        entry = run_rule(name, make_alt_rate(name, stats), short_pools, sheriff, DIAG_SEED)
        entry["rating_stats"] = stats
        report["rules"]["alt:" + name] = entry
        print(name, entry.get("metrics"), entry.get("failure"), entry["seconds"], flush=True)
        save()


if __name__ == "__main__":
    main()
