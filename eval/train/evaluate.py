#!/usr/bin/env python3
"""Visible train-slice evaluation for the deviation-rating benchmark.

Runs the rating program ``scripts/rate.sh`` on the five documented public games
(paper Table 2 biased Shapley game, cloned rock-paper-scissors, the general-sum
reference game with a [0.3, 0.7] mixture and with fixed offsets, and the 2x2
dominance game), applies the validity gates in eval/protocol.py, and writes
scoring/scores_train.json. Run with ``python3 -I``.
"""

from __future__ import annotations

import sys

sys.path.insert(0, "/home/user")

from eval.protocol import ROOT, evaluate_public  # noqa: E402


def main() -> dict:
    scores = evaluate_public(ROOT / "scoring" / "scores_train.json", "train (public games)")
    print("Train evaluation complete. Results written to scoring/scores_train.json")
    return scores


if __name__ == "__main__":
    main()
