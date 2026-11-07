#!/usr/bin/env python3
"""Mechanical before/after comparison of every shortcut against the reference.

"before" compares redteam/<name>/before_hardening/scores_test.json with the
pre-hardening reference (redteam/reference_seeds/seed_0/scores_test.json);
"after" compares redteam/<name>/scores_test.json with the hardened reference
(redteam/reference_runs/run_0/scores_test.json). Only the proposed-method
entry decides the verdict; baseline rows are checked for tampering separately.
No aggregate rank is invented.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path("/home/user/redteam")
PROPOSED = "deviation_rating"
HIGHER_IS_BETTER = {"min_margin"}
FAIL_MAGNITUDE = 1.0e6


def load(path: Path):
    return json.loads(path.read_text()) if path.is_file() else None


def compare(scores: dict, reference: dict) -> dict:
    better, worse, nonfinite, failed, baseline_changed = [], [], [], [], []
    for experiment, entry in reference["experiments"].items():
        ref_row = entry["results"][PROPOSED]
        row = scores.get("experiments", {}).get(experiment, {}).get("results", {}).get(PROPOSED)
        if row is None:
            worse.append(f"{experiment}: missing")
            continue
        if any(isinstance(v, (int, float)) and abs(v) >= FAIL_MAGNITUDE for v in row.values()):
            failed.append(experiment)
        for metric, ref_value in ref_row.items():
            value = row.get(metric)
            label = f"{experiment}.{metric}"
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                worse.append(f"{label}: missing")
            elif not math.isfinite(value):
                nonfinite.append(f"{label}={value}")
            elif value != ref_value:
                is_better = (value > ref_value) == (metric in HIGHER_IS_BETTER)
                (better if is_better else worse).append(f"{label}: {ref_value} -> {value}")
        for method, ref_metrics in entry["results"].items():
            if method != PROPOSED and scores["experiments"].get(experiment, {}).get("results", {}).get(method) != ref_metrics:
                baseline_changed.append(f"{experiment}.{method}")
    if nonfinite:
        verdict = "accepted with non-finite scores"
    elif better and not worse:
        verdict = "BEATS the reference"
    elif not better and not worse:
        verdict = "ties the reference (no gain)"
    elif better:
        verdict = "mixed (some metrics better, some worse)"
    elif failed:
        verdict = "scored as failed in " + ", ".join(failed)
    else:
        verdict = "worse than the reference"
    return {"verdict": verdict, "better": better, "worse": worse, "nonfinite": nonfinite,
            "failed_experiments": failed, "baseline_rows_changed": baseline_changed}


def side(folder: Path, reference: dict, before: bool) -> dict:
    base = folder / "before_hardening" if before else folder
    status = load(base / "status.json") or {}
    scores = load(base / "scores_test.json")
    row = {"test_exit_code": status.get("test", {}).get("exit_code"),
           "attack_markers": status.get("attack_markers", [])}
    if scores is None:
        row["verdict"] = f"no test score (test exit code {row['test_exit_code']})"
    else:
        row.update(compare(scores, reference))
    return row


def main() -> None:
    reference = load(ROOT / "reference_runs/run_0/scores_test.json")
    before_reference = load(ROOT / "reference_seeds/seed_0/scores_test.json")
    runs = sorted((ROOT / "reference_runs").glob("run_*/scores_test.json"))
    identical = all(load(path) == reference for path in runs)
    comparisons = {"reference_runs": len(runs), "reference_runs_identical": identical, "shortcuts": {}}
    for name in json.loads((ROOT / "shortcut_cases.json").read_text()):
        folder = ROOT / name
        entry = {"after": side(folder, reference, before=False)}
        if (folder / "before_hardening").is_dir() and before_reference is not None:
            entry["before"] = side(folder, before_reference, before=True)
        comparisons["shortcuts"][name] = entry
    (ROOT / "shortcut_comparisons.json").write_text(json.dumps(comparisons, indent=2))
    for name, entry in comparisons["shortcuts"].items():
        before = entry.get("before", {}).get("verdict", "(new probe)")
        print(f"{name:<38} before: {before:<45} after: {entry['after']['verdict']}")
    print(f"reference runs: {len(runs)}, identical: {identical}")


if __name__ == "__main__":
    main()
