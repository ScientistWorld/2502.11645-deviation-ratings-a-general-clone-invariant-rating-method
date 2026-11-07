#!/usr/bin/env python3
"""Run the hidden test's population loop in-process with the reference, game by game.

Diagnostic for job 3, where the hidden test stalled: every meta-game is rated
under a 120 s alarm, and per-iteration time, the slowest game, LP fallback
attempts and gate results are printed. Only aggregate numbers are written
(redteam/hidden_population_check.json); no hidden game is stored.
"""

from __future__ import annotations

import importlib.util
import json
import signal
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path("/home/user")
sys.path.insert(0, str(ROOT))

from method.deviation_rating import deviation_rating  # noqa: E402

spec = importlib.util.spec_from_file_location("hidden_eval", ROOT / "eval/test/evaluate.py")
H = importlib.util.module_from_spec(spec)
spec.loader.exec_module(H)


class Stall(Exception):
    pass


def _alarm(signum, frame):
    raise Stall()


def main() -> None:
    signal.signal(signal.SIGALRM, _alarm)
    seed = H._mix(H.HIDDEN_SEED, 0x50)
    sheriff, pools = H.make_pools(seed)
    loop = H.PopulationLoop(sheriff, pools, seed)
    report = {"iterations": [], "stalls": 0, "gate_failures": 0, "fallback_attempts": 0, "slowest_game_s": 0.0}
    for it in range(H.POP_ITERATIONS):
        t0 = time.monotonic()
        ratings = []
        for game in loop.meta_games():
            g0 = time.monotonic()
            signal.alarm(120)
            try:
                arr = np.asarray(game.payload(), dtype=float)
                res = deviation_rating(arr, game.n, list(game.dims))
                signal.alarm(0)
            except Stall:
                report["stalls"] += 1
                print(f"iteration {it + 1}: STALL (> 120 s)", flush=True)
                ratings.append(H.uniform_ratings(game))
                continue
            except Exception as error:
                signal.alarm(0)
                print(f"iteration {it + 1}: error {error}", flush=True)
                report["gate_failures"] += 1
                ratings.append(H.uniform_ratings(game))
                continue
            report["fallback_attempts"] += res["fallback_attempts"]
            report["slowest_game_s"] = max(report["slowest_game_s"], time.monotonic() - g0)
            sigma = [float(x) for x in res["equilibrium"]]
            out = {"ratings": [[res["ratings_dict"][p][a] for a in range(game.dims[p])] for p in range(game.n)],
                   "equilibrium": sigma}
            check = H.validate_result(game, out)
            if not check["ok"]:
                report["gate_failures"] += 1
                print(f"iteration {it + 1}: gate failure {check['reason']}", flush=True)
                ratings.append(H.uniform_ratings(game))
            else:
                ratings.append(check["ratings"])
        loop.advance(ratings)
        report["iterations"].append(round(time.monotonic() - t0, 2))
        if (it + 1) % 16 == 0:
            print(f"iteration {it + 1}: {sum(report['iterations']):.0f} s total, slowest game "
                  f"{report['slowest_game_s']:.2f} s, fallbacks {report['fallback_attempts']}", flush=True)
    report["metrics"] = loop.metrics()
    report["mean_curve"] = loop.mean_curve()
    print(json.dumps({k: v for k, v in report.items() if k != "iterations"}), flush=True)
    (ROOT / "redteam/hidden_population_check.json").write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
