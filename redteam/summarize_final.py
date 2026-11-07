#!/usr/bin/env python3
"""Compare every final replay (redteam/<name>/final/scores_test.json) with the reference.

The reference is redteam/reference_runs/run_0/final/scores_test.json (the three
reference runs are checked to be identical). For each shortcut and experiment:
'F' = scored as failed (every proposed metric at the failure value), 'R' = equal
to the reference, otherwise 'worse', 'better' or 'mixed' by metric direction.
'Before' is the score REDTEAM.md reported for the pre-hardening test.
Writes redteam/final_comparisons.json and prints a markdown table.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path("/home/user")
sys.path.insert(0, str(ROOT / "redteam"))
from replay_all import cases  # noqa: E402

HIGHER = {"min_margin"}
FAIL = 1.0e6


def load(path: Path):
    return json.loads(path.read_text())["experiments"] if path.is_file() else None


def classify(entry: dict, ref: dict) -> str:
    if all(abs(v) == FAIL for v in entry.values()):
        return "F"
    better = worse = False
    for metric, value in entry.items():
        r = ref[metric]
        if value == r:
            continue
        if (value > r) == (metric in HIGHER):
            better = True
        else:
            worse = True
    if better and worse:
        return "mixed"
    return "better" if better else ("worse" if worse else "R")


def redteam_before() -> dict:
    text = (ROOT / "REDTEAM.md").read_text()
    out = {}
    for line in text.splitlines():
        m = re.match(r"\| \[(\w+)\]\(redteam/\w+/run\.sh\) \| (.*?) \| \[(.*?)\]\(.*?\) \| (.*?) \|$", line)
        if m:
            out[m.group(1)] = {"what": m.group(2), "score": m.group(3), "verdict": m.group(4)}
    return out


def main() -> None:
    ref = load(ROOT / "redteam/reference_runs/run_0/final/scores_test.json")
    refs = [load(ROOT / f"redteam/reference_runs/run_{k}/final/scores_test.json") for k in range(2)]
    refs.append(load(ROOT / "scoring/scores_test.json"))
    identical = all(r == ref for r in refs if r is not None)
    before = redteam_before()
    rows = {}
    for kind, name in cases():
        if kind == "reference":
            continue
        scores = load(ROOT / "redteam" / name / "final/scores_test.json")
        status_path = ROOT / "redteam" / name / "final/status.json"
        status = json.loads(status_path.read_text()) if status_path.is_file() else {}
        if scores is None:
            rows[name] = {"pending": True}
            continue
        per = {}
        for experiment, entry in scores.items():
            per[experiment] = classify(entry["results"]["deviation_rating"], ref[experiment]["results"]["deviation_rating"])
        verdicts = set(per.values())
        if verdicts == {"F"}:
            overall = "failed in all 6 experiments"
        elif "better" in verdicts or "mixed" in verdicts:
            overall = "BEATS OR MIXES WITH THE REFERENCE"
        elif verdicts == {"R"}:
            overall = "ties the reference"
        else:
            failed = [e for e, v in per.items() if v == "F"]
            worse = [e for e, v in per.items() if v == "worse"]
            parts = []
            if failed:
                parts.append("failed in " + ", ".join(failed))
            if worse:
                parts.append("worse in " + ", ".join(worse))
            overall = "; ".join(parts) + ("; ties elsewhere" if "R" in verdicts else "")
        rows[name] = {"per_experiment": per, "overall": overall, "before": before.get(name),
                      "markers": status.get("attack_markers") or status.get("shortcut_writer_marker_at_capture"),
                      "population": scores["population_improvement"]["results"]["deviation_rating"]}
    report = {"reference_runs_identical": identical, "reference": {e: v["results"] for e, v in ref.items()},
              "shortcuts": rows}
    (ROOT / "redteam/final_comparisons.json").write_text(json.dumps(report, indent=1))
    print("reference runs identical:", identical)
    for name, row in rows.items():
        print(f"{name}: {row.get('overall', 'PENDING')}  pop={row.get('population')}")


if __name__ == "__main__":
    main()
