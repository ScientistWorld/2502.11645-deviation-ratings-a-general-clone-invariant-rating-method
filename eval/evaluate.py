#!/usr/bin/env python3
"""Standard evaluation entrypoint (scripts/evaluate.sh) for the public games.

Identical protocol to the visible train slice (eval/train/evaluate.py): runs the
rating program ``scripts/rate.sh`` on the five documented public games, applies
the validity gates in eval/protocol.py, and writes scoring/scores.json.
Run with ``python3 -I``.
"""

from __future__ import annotations

import sys

sys.path.insert(0, "/home/user")

from eval.protocol import ROOT, evaluate_public  # noqa: E402


def main() -> dict:
    scores = evaluate_public(ROOT / "scoring" / "scores.json", "evaluate (public games)")
    print("Evaluation complete. Results written to scoring/scores.json")
    return scores


if __name__ == "__main__":
    main()
