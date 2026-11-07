#!/usr/bin/env python3
"""Hardening diagnostics: run rating programs through the hidden-test protocol
under the official hidden seed and several alternative seeds.

Answers three questions with numbers instead of assumptions:
  * does the reference method score exactly on the hidden families (and on
    families drawn with other seeds, i.e. beyond one lucky draw)?
  * how far are its outputs from the tolerances (rating mismatch, CCE gain)?
  * do cheap equilibrium selections that skip the paper's sequential LP fail?

Only aggregate metrics are written (redteam/diagnostics.json); hidden games and
per-game outputs are not.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path

ROOT = Path("/home/user")
SPEC = importlib.util.spec_from_file_location("hidden_test", ROOT / "eval/test/evaluate.py")
HIDDEN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HIDDEN)

RATER = ["python3", str(ROOT / "redteam/shortcut_rater.py")]
PROGRAMS = {
    "reference (scripts/rate.sh)": ["bash", str(ROOT / "scripts/rate.sh")],
    "reference, dual-only freezing": RATER + ["variant:dual"],
    "reference, dual-only freezing, tight LP tolerances": RATER + ["variant:dual_tight"],
    "reference, tight LP tolerances": RATER + ["variant:active_tight"],
    "single LP (first step of Algorithm 1 only)": RATER + ["single_lp_shortcut"],
    "any CCE (feasibility LP)": RATER + ["feasibility_cce_shortcut"],
    "first pure Nash equilibrium": RATER + ["pure_nash_shortcut"],
    "deviation gains at the uniform distribution": RATER + ["uniform_gains_shortcut"],
}


def main(argv) -> None:
    seeds = [HIDDEN.HIDDEN_SEED] + [int(s) for s in argv[1:]] if len(argv) > 1 else [HIDDEN.HIDDEN_SEED, 11, 22, 33, 44]
    report = {"seeds": ["hidden" if s == HIDDEN.HIDDEN_SEED else s for s in seeds], "programs": {}}
    for label, command in PROGRAMS.items():
        rows = []
        for seed in seeds:
            start = time.monotonic()
            scores, diagnostics = HIDDEN.evaluate_hidden(seed=seed, command=command)
            elapsed = time.monotonic() - start
            row = {"seed": "hidden" if seed == HIDDEN.HIDDEN_SEED else seed, "seconds": round(elapsed, 1),
                   "rater_error": diagnostics["rater_error"], "experiments": {}}
            for experiment, entry in scores["experiments"].items():
                diag = diagnostics["experiments"][experiment]
                row["experiments"][experiment] = {
                    "proposed": entry["results"]["deviation_rating"],
                    "uniform_payoff": entry["results"]["uniform_payoff"],
                    "failed_games": diag["failed_games"],
                    "failure_reasons": diag["failure_reasons"][:3],
                    "max_rating_mismatch": diag["max_rating_mismatch"],
                    "max_deviation_gain": diag["max_deviation_gain"],
                }
            rows.append(row)
            compact = {exp: ("FAILED" if v["failed_games"] else v["proposed"]) for exp, v in row["experiments"].items()}
            print(f"[{label}] seed={row['seed']} {elapsed:.1f}s {json.dumps(compact)}", flush=True)
        report["programs"][label] = rows
    out = ROOT / "redteam/diagnostics.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main(sys.argv)
