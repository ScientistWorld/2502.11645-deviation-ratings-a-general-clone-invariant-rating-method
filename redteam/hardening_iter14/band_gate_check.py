"""Direct check of the noise-bound gate of the hidden test (iteration 14), pure Python.

The container replay of band_violation_shortcut stalled (see HARDENING.md), so this
diagnostic calls the hidden evaluator's own validate_result on every noisy observation
of the hidden suite. It submits the reference-free outputs below and records the verdict:

* moved_2b:  'payoffs' moved by twice the noise bound -> must fail with the band reason;
* moved_b:   'payoffs' moved by exactly the bound (in band) -> must pass the band check
             (it then fails or passes the CCE check on its own merits);
* malformed: 'payoffs' with a wrong shape -> must fail;
* exact game with out-of-band 'payoffs': the field is ignored (no noise bound).

Usage: python3 redteam/hardening_iter14/band_gate_check.py
"""
from __future__ import annotations

import importlib.util
import json
from collections import Counter
from pathlib import Path

ROOT = Path("/home/user")


def main():
    spec = importlib.util.spec_from_file_location("ev", ROOT / "eval/test/evaluate.py")
    ev = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ev)
    suite = ev.build_hidden_suite()
    verdicts = {name: Counter() for name in ("moved_2b", "moved_b", "malformed", "exact_game_out_of_band")}
    for gid, bound in suite.noise.items():
        game = suite.games[gid]
        sigma = [1.0 / game.size] * game.size
        for name, shift in (("moved_2b", 2 * bound), ("moved_b", bound)):
            moved = ev.Game(game.dims, [[v + shift for v in t] for t in game.tables])
            gains = ev.deviation_gains(moved, sigma)
            entry = {"ratings": gains, "equilibrium": sigma, "payoffs": moved.payload()}
            check = ev.validate_result(game, entry, bound)
            band = "noise bound" in check["reason"]
            verdicts[name]["band_failure" if band else ("ok" if check["ok"] else "other_failure")] += 1
        entry = {"ratings": ev.deviation_gains(game, sigma), "equilibrium": sigma, "payoffs": [[1.0]]}
        check = ev.validate_result(game, entry, bound)
        verdicts["malformed"]["shape_failure" if "'payoffs' must" in check["reason"] else "other"] += 1
    # An exact property game ignores 'payoffs' entirely: the gate uses the game itself.
    exact = next(gid for gid in suite.games if gid not in suite.noise and suite.games[gid].size <= 16)
    game = suite.games[exact]
    sigma = [1.0 / game.size] * game.size
    far = ev.Game(game.dims, [[v + 10.0 for v in t] for t in game.tables])
    check = ev.validate_result(game, {"ratings": ev.deviation_gains(game, sigma), "equilibrium": sigma,
                                      "payoffs": far.payload()}, 0.0)
    verdicts["exact_game_out_of_band"]["band_failure" if "noise bound" in check["reason"] else "field_ignored"] += 1
    out = {name: dict(counter) for name, counter in verdicts.items()}
    out["noisy_observations"] = len(suite.noise)
    (ROOT / "redteam/hardening_iter14/band_gate_check.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
