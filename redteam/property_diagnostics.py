#!/usr/bin/env python3
"""Property-suite diagnostics: the hidden test's five property experiments on the
official hidden seed and six alternative seeds, rated in-process (no per-call
process overhead) by the reference and by cheap equilibrium selections.

Questions answered with numbers:
  * does the reference score exactly 0 on every property metric, including the
    new strictness_gap, on every suite (not one lucky draw)?
  * do cheaper selections fail: the lexicographically least strict CCE ("lax"),
    a CCE with all non-dominated gains forced to 0 ("zero_gain"), the first LP of
    Algorithm 1 only, any feasible CCE?
  * how close is the evaluator's certified strictest epsilon to the reference's
    largest deviation gain (it must not penalise the reference)?

Only aggregate metrics are written (redteam/property_diagnostics.json).
"""

from __future__ import annotations

import importlib.util
import json
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
pspec = importlib.util.spec_from_file_location("population_diag", ROOT / "redteam/population_diagnostics.py")


def as_output(game, sigma):
    sigma = np.maximum(np.asarray(sigma, dtype=float), 0.0)
    sigma = list(sigma / sigma.sum())
    return {"ratings": H.deviation_gains(game, sigma), "equilibrium": sigma}


def zero_gain(game):
    D = np.asarray(H.deviation_rows(game), dtype=float)
    k, m = D.shape
    eq, rhs = [np.ones(m)], [1.0]
    row = 0
    for p in range(game.n):
        for a in range(game.dims[p]):
            dominated = any(
                all(game.tables[p][j + (b - game._own[p][j]) * game.strides[p]] >
                    game.tables[p][j + (a - game._own[p][j]) * game.strides[p]] + 1e-9
                    for j in range(game.size) if game._own[p][j] == 0)
                for b in range(game.dims[p]) if b != a)
            if not dominated:
                eq.append(D[row])
                rhs.append(0.0)
            row += 1
    res = linprog(np.zeros(m), A_ub=D, b_ub=np.zeros(k), A_eq=np.array(eq), b_eq=rhs, bounds=(0, None), method="highs")
    if not res.success:
        res = linprog(np.zeros(m), A_ub=D, b_ub=np.zeros(k), A_eq=[np.ones(m)], b_eq=[1.0], bounds=(0, None), method="highs")
    return as_output(game, res.x)


def feasibility(game):
    D = np.asarray(H.deviation_rows(game), dtype=float)
    k, m = D.shape
    res = linprog(np.zeros(m), A_ub=D, b_ub=np.zeros(k), A_eq=[np.ones(m)], b_eq=[1.0], bounds=(0, None), method="highs")
    return as_output(game, res.x)


def main() -> None:
    P = importlib.util.module_from_spec(pspec)
    pspec.loader.exec_module(P)
    rules = {
        "reference": lambda g: rate_game(g.payload()),
        "lax": lambda g: as_output(g, _sigma_from_gains_rule(P, g, "lax")),
        "single_lp": lambda g: as_output(g, _sigma_from_gains_rule(P, g, "single_lp")),
        "zero_gain": zero_gain,
    }
    seeds = [H.HIDDEN_SEED, 101, 202, 303, 404]
    report = {"seeds": ["hidden" if s == H.HIDDEN_SEED else s for s in seeds], "rules": {}}
    for name, rule in rules.items():
        rows = []
        for seed in seeds:
            start = time.monotonic()
            suite = H.build_hidden_suite(seed)
            strictest = {gid: H.strictest_epsilon(g) for gid, g in suite.games.items()}
            results, slack = {}, []
            for gid, game in suite.games.items():
                out = rule(game)
                results[gid] = out
                check = H.validate_result(game, out)
                if check.get("ok") and strictest[gid] is not None:
                    slack.append((check["max_gain"] - strictest[gid][1]) / game.scale())
            scores, diag = H.score_suite(suite.games, suite.instances, results, {}, strictest)
            row = {"seed": "hidden" if seed == H.HIDDEN_SEED else seed, "seconds": round(time.monotonic() - start, 1),
                   "uncertified": sum(1 for v in strictest.values() if v is None),
                   "max_relative_excess_over_strictest": max(slack) if slack else None,
                   "experiments": {e: {"proposed": v["results"]["deviation_rating"],
                                       "failed_games": diag["experiments"][e]["failed_games"],
                                       "failure_reasons": diag["experiments"][e]["failure_reasons"][:2]}
                                   for e, v in scores["experiments"].items()}}
            rows.append(row)
            compact = {e: ("FAILED" if v["failed_games"] else v["proposed"]) for e, v in row["experiments"].items()}
            print(f"[{name}] seed={row['seed']} {row['seconds']}s excess={row['max_relative_excess_over_strictest']} "
                  f"{json.dumps(compact)}", flush=True)
        report["rules"][name] = rows
        (ROOT / "redteam/property_diagnostics.json").write_text(json.dumps(report, indent=1))


def _sigma_from_gains_rule(P, game, rule):
    # P.lp_gains returns gains; recompute the distribution with the same LPs.
    D = np.asarray(H.deviation_rows(game), dtype=float)
    k, m = D.shape
    if rule == "single_lp":
        res = linprog(np.r_[np.zeros(m), 1.0], A_ub=np.c_[D, -np.ones(k)], b_ub=np.zeros(k),
                      A_eq=[np.r_[np.ones(m), 0.0]], b_eq=[1.0], bounds=[(0, None)] * m + [(None, None)],
                      method="highs")
        return res.x[:m]
    frozen, sigma = {}, None
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
    return sigma


if __name__ == "__main__":
    main()
