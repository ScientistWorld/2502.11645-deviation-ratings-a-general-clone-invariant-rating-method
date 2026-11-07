#!/usr/bin/env python3
"""Population-improvement diagnostics (paper Section 5.3) on NON-hidden seeds.

Uses the hidden test's own loop machinery (eval/test/evaluate.py: Sheriff game,
candidate streams, tie-breaking, maximum-entropy CCE gap) with in-process rating
rules, so many seeds and long horizons fit in one job:

* reference: method.rate.rate_game (the paper's sequential LP);
* uniform_payoff, random_selection: the evaluator's baselines;
* alternative CCE selections (to show the experiment has headroom and is not
  saturated): the lexicographically *least* strict CCE ("lax"), the first LP of
  Algorithm 1 only, and the maximum-welfare CCE.

Curves are recorded every 8 iterations up to --iterations, so metrics for any
shorter horizon are the same runs truncated. Writes redteam/population_diagnostics.json.
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

from method.rate import rate_game  # noqa: E402

spec = importlib.util.spec_from_file_location("hidden_eval", ROOT / "eval/test/evaluate.py")
H = importlib.util.module_from_spec(spec)
spec.loader.exec_module(H)

SEEDS = (101, 202, 303, 404, 505, 606)


def coeff(game) -> np.ndarray:
    return np.asarray(H.deviation_rows(game), dtype=float)


def lp_gains(game, rule: str):
    D = coeff(game)
    k, m = D.shape
    if rule == "single_lp":
        c = np.r_[np.zeros(m), 1.0]
        res = linprog(c, A_ub=np.c_[D, -np.ones(k)], b_ub=np.zeros(k), A_eq=[np.r_[np.ones(m), 0.0]], b_eq=[1.0],
                      bounds=[(0, None)] * m + [(None, None)], method="highs")
        sigma = res.x[:m]
    elif rule == "max_welfare":
        c = -np.sum(np.asarray(game.tables), axis=0)
        res = linprog(c, A_ub=D, b_ub=np.zeros(k), A_eq=[np.ones(m)], b_eq=[1.0], bounds=(0, None), method="highs")
        sigma = res.x
    elif rule == "lax":
        frozen = {}
        sigma = None
        while len(frozen) < k:
            todo = [i for i in range(k) if i not in frozen]
            upper = np.c_[D, np.zeros(k)]
            lower = np.c_[-D[todo], np.ones(len(todo))]
            eq = [np.r_[np.ones(m), 0.0]] + [np.r_[D[i], 0.0] for i in frozen]
            rhs = [1.0] + list(frozen.values())
            res = linprog(np.r_[np.zeros(m), -1.0], A_ub=np.r_[upper, lower], b_ub=np.zeros(k + len(todo)),
                          A_eq=eq, b_eq=rhs, bounds=[(0, None)] * m + [(None, None)], method="highs")
            sigma = res.x[:m]
            chosen = [i for j, i in enumerate(todo) if abs(res.ineqlin.marginals[k + j]) > 1e-8]
            if not chosen:
                chosen = [todo[int(np.argmin(D[todo] @ sigma))]]
            for i in chosen:
                frozen[i] = float(D[i] @ sigma)
    else:
        raise ValueError(rule)
    sigma = np.maximum(sigma, 0.0)
    return H.deviation_gains(game, list(sigma / sigma.sum()))


def run_loop(seed: int, rate, iterations: int) -> dict:
    H.POP_ITERATIONS = iterations
    sheriff, pools = H.make_pools(seed)
    loop = H.PopulationLoop(sheriff, pools, seed)
    start = time.perf_counter()
    for _ in range(iterations):
        loop.advance([rate(game) for game in loop.meta_games()])
    return {"curves": [[round(v, 5) for v in c] for c in loop.curves], "seconds": round(time.perf_counter() - start, 1)}


def run_baseline(seed: int, name: str, iterations: int) -> dict:
    H.POP_ITERATIONS = iterations
    sheriff, pools = H.make_pools(seed)
    start = time.perf_counter()
    loop = H.baseline_population(sheriff, pools, seed, name)
    return {"curves": [[round(v, 5) for v in c] for c in loop.curves], "seconds": round(time.perf_counter() - start, 1)}


def metrics_at(curves, horizon: int) -> dict:
    points = horizon // H.POP_CHECKPOINT_EVERY
    initial = sum(c[0] for c in curves) / len(curves)
    later = [v for c in curves for v in c[1:points + 1]]
    late = [v for c in curves for v in c[points // 2 + 1:points + 1]]
    final = sum(c[points] for c in curves) / len(curves)
    return {"mean_gap_ratio": round(sum(later) / len(later) / initial, 6),
            "late_gap_ratio": round(sum(late) / len(late) / initial, 6),
            "final_gap_ratio": round(final / initial, 6)}


def reference_rate(game):
    out = rate_game(game.payload())
    check = H.validate_result(game, out)
    if not check["ok"]:
        raise RuntimeError(check["reason"])
    return check["ratings"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=128)
    parser.add_argument("--alt-iterations", type=int, default=64)
    parser.add_argument("--alt-seeds", type=int, default=3)
    parser.add_argument("--out", default=str(ROOT / "redteam/population_diagnostics.json"))
    args = parser.parse_args()
    report = {"seeds": list(SEEDS), "iterations": args.iterations, "checkpoint_every": H.POP_CHECKPOINT_EVERY,
              "runs_per_seed": H.POP_RUNS, "rules": {}}

    def save():
        horizons = [h for h in (32, 64, 96, 128, 160, 192, 256) if h <= args.iterations]
        summary = {}
        for rule, per_seed in report["rules"].items():
            summary[rule] = {}
            for h in horizons:
                vals = [metrics_at(v["curves"], h) for v in per_seed.values()
                        if "curves" in v and len(v["curves"][0]) > h // H.POP_CHECKPOINT_EVERY]
                if vals:
                    summary[rule][str(h)] = {
                        m: {"per_seed": [x[m] for x in vals], "mean": round(sum(x[m] for x in vals) / len(vals), 6)}
                        for m in ("mean_gap_ratio", "late_gap_ratio", "final_gap_ratio")
                    }
        report["summary"] = summary
        Path(args.out).write_text(json.dumps(report, indent=1))

    for seed in SEEDS:
        for name in ("uniform_payoff", "random_selection"):
            report["rules"].setdefault(name, {})[str(seed)] = run_baseline(seed, name, args.iterations)
        report["rules"].setdefault("reference", {})[str(seed)] = run_loop(seed, reference_rate, args.iterations)
        print(seed, {r: metrics_at(v[str(seed)]["curves"], args.iterations) for r, v in report["rules"].items()},
              report["rules"]["reference"][str(seed)]["seconds"], "s", flush=True)
        save()
    for rule in ("lax", "single_lp", "max_welfare"):
        for seed in SEEDS[: args.alt_seeds]:
            try:
                entry = run_loop(seed, lambda g, r=rule: lp_gains(g, r), args.alt_iterations)
            except Exception as error:  # report, do not abort the diagnostics
                entry = {"error": repr(error)}
            report["rules"].setdefault(rule, {})[str(seed)] = entry
            print(rule, seed, metrics_at(entry["curves"], args.alt_iterations) if "curves" in entry else entry, flush=True)
            save()


if __name__ == "__main__":
    main()
