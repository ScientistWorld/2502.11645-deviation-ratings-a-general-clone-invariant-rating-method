"""The REDTEAM's public three-LP witness, scored with the hardened evaluator's block strictness.

Game: paper Table 2 (biased Shapley with N, 4x4) times an independent six-action
bystander with payoffs 0, -0.01, ..., -0.05 (redteam/current_audit/three_lp_shortcut/
witness_input.json). Runs the reference and the capped variants standalone and
reports, per independent block, the excess of the returned equilibrium's largest
deviation gain over the block's certified strictest value (the quantity
`strictness_gap` now scores). No hidden games are involved.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path("/home/user")
sys.path.insert(0, str(ROOT))
from redteam.hardening_final.rating_program import candidate  # noqa: E402

spec = importlib.util.spec_from_file_location("hidden_eval", ROOT / "eval/test/evaluate.py")
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)


def main():
    payload = json.loads((ROOT / "redteam/current_audit/three_lp_shortcut/witness_input.json").read_text())["games"][0]
    payoffs = np.asarray(payload["payoffs"], dtype=float)
    dims = list(payoffs.shape[1:])
    game = ev.Game(dims, [payoffs[p].reshape(-1).tolist() for p in range(len(dims))])
    blocks = [(0, 1), (2,)]
    certified = ev.block_strictness(game, blocks)
    records = {"dims": dims, "blocks": [list(b) for b in blocks],
               "certified_block_strictest": [bounds[1] for _, bounds in certified], "modes": {}}
    for mode in ("reference", "three_lp_shortcut", "two_lp_shortcut", "weaker_one_lp", "active_freeze_variant"):
        out = candidate(payoffs, mode)
        check = ev.validate_result(game, out)
        excess = [max(0.0, max(check["player_max"][p] for p in b) - bounds[1]) for b, bounds in certified]
        records["modes"][mode] = {"gates_ok": check["ok"], "reason": check["reason"],
                                  "block_max_gain": [max(check["player_max"][p] for p in b) for b in blocks],
                                  "block_excess": excess, "strictness_gap": ev._err(max(excess), game.scale()),
                                  "ratings": out["ratings"]}
    (ROOT / "redteam/hardening_final/witness.json").write_text(json.dumps(records, indent=2))
    print(json.dumps({m: (r["gates_ok"], r["strictness_gap"]) for m, r in records["modes"].items()}), flush=True)


if __name__ == "__main__":
    main()
