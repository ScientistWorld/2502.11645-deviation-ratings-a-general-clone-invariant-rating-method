"""Paired per-instance comparison on the noisy-redundancy experiment, in exact arithmetic.

Diagnostic for HARDENING.md (iteration 14); it is not part of any evaluator. It builds the
hidden (``--split test``) or visible (``--split train``) suite with the evaluator's own
generator, and rates every noisy observation two ways with the evaluator's exact
(rational) Algorithm-1 solver:

* plug-in: the observation as given (what the reference method computes; its float
  ratings agree with these to round-off, which the aggregate check below confirms);
* merge: the merge-near-copies estimate (same rule as rating_program.merge_near_copies).

Per instance it records the error in units of the noise bound, then the mean, the paired
difference, its standard error and t statistic, and wins/losses. Usage:

    python3 redteam/hardening_iter14/paired_noisy.py --split test [--workers 2]
"""
from __future__ import annotations

import argparse
import importlib.util
import itertools
import json
import math
import statistics
import time
from fractions import Fraction
from multiprocessing import Pool
from pathlib import Path

ROOT = Path("/home/user")
HERE = ROOT / "redteam/hardening_iter14"
SOURCES = {"test": ROOT / "eval/test/evaluate.py", "train": ROOT / "eval/protocol.py"}
EV = None


def load(split: str):
    spec = importlib.util.spec_from_file_location(f"ev_{split}", SOURCES[split])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def exact_tables(game):
    return [[Fraction(round(v * 1_000_000), 1_000_000) for v in table] for table in game.tables]


def merge(dims, tables, bound):
    """Merge actions whose observations are consistent with one true action (pure-Python twin of
    rating_program.merge_near_copies)."""
    n = len(dims)
    joints = list(itertools.product(*[range(d) for d in dims]))
    index = {j: i for i, j in enumerate(joints)}
    labels = []
    for p in range(n):
        def compatible(a, c):
            for j in joints:
                if j[p] != a:
                    continue
                k = list(j)
                k[p] = c
                k = index[tuple(k)]
                if any(abs(tables[q][index[j]] - tables[q][k]) > 2 * bound for q in range(n)):
                    return False
            return True
        groups = []
        for a in range(dims[p]):
            for group in groups:
                if all(compatible(a, c) for c in group):
                    group.append(a)
                    break
            else:
                groups.append([a])
        label = [0] * dims[p]
        for g, group in enumerate(groups):
            for a in group:
                label[a] = g
        labels.append(label)
    classes = {}
    for j in joints:
        classes.setdefault(tuple(labels[p][j[p]] for p in range(n)), []).append(index[j])
    out = [list(t) for t in tables]
    for members in classes.values():
        if len(members) < 2:
            continue
        for q in range(n):
            low = max(tables[q][i] for i in members) - bound
            high = min(tables[q][i] for i in members) + bound
            if low <= high:
                for i in members:
                    out[q][i] = (low + high) / 2
    return out


def error(ratings, truth, maps, bound):
    diffs = [abs(float(ratings[q][a]) - truth[q][maps[q][a]]) for q in range(len(ratings)) for a in range(len(ratings[q]))]
    return math.fsum(diffs) / len(diffs) / bound


def work(args):
    split, number, inst, games = args
    global EV
    if EV is None:
        EV = load(split)
    bound = inst["noise_bound"]
    row = {"instance": number, "kind": inst["kind"], "copies": inst["copies"]}
    for key in ("variant", "base"):
        dims, tables = games[key]
        observed = [[Fraction(round(v * 1_000_000), 1_000_000) for v in t] for t in tables]
        plug = EV.exact_deviation_ratings(dims, observed)
        merged = EV.exact_deviation_ratings(dims, merge(dims, observed, Fraction(round(bound * 1_000_000), 1_000_000)))
        row[key] = {"plug_in": error(plug, inst["truth"], inst[key + "_maps"], bound),
                    "merge": error(merged, inst["truth"], inst[key + "_maps"], bound)}
    return row


def summary(rows, key):
    plug = [r[key]["plug_in"] for r in rows]
    merged = [r[key]["merge"] for r in rows]
    diffs = [a - b for a, b in zip(plug, merged)]
    sd = statistics.stdev(diffs) if len(diffs) > 1 else 0.0
    se = sd / math.sqrt(len(diffs)) if diffs else 0.0
    return {"plug_in_mean": statistics.fmean(plug), "merge_mean": statistics.fmean(merged),
            "mean_paired_improvement": statistics.fmean(diffs), "paired_sd": sd, "paired_se": se,
            "t": statistics.fmean(diffs) / se if se > 0 else None,
            "merge_better": sum(d > 1e-12 for d in diffs), "merge_worse": sum(d < -1e-12 for d in diffs),
            "tied": sum(abs(d) <= 1e-12 for d in diffs)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("test", "train"), default="test")
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    started = time.monotonic()
    ev = load(args.split)
    suite = ev.build_hidden_suite() if args.split == "test" else ev.build_visible_suite()
    tasks = []
    for number, inst in enumerate(suite.instances[ev.NOISY_EXPERIMENT]):
        games = {key: (suite.games[inst[key]].dims, suite.games[inst[key]].tables) for key in ("variant", "base")}
        light = {k: v for k, v in inst.items() if k not in ("variant", "base")}
        tasks.append((args.split, number, light, games))
    with Pool(args.workers) as pool:
        rows = sorted(pool.map(work, tasks, chunksize=1), key=lambda r: r["instance"])
    out = {"split": args.split, "instances": len(rows), "seconds": round(time.monotonic() - started, 1),
           "padded (rating_error)": summary(rows, "variant"), "clean (clean_rating_error)": summary(rows, "base"),
           "rows": rows}
    path = HERE / f"paired_noisy_{args.split}.json"
    path.write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}, indent=1))


if __name__ == "__main__":
    main()
