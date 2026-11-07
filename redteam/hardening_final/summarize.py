"""Before/after comparison of the replayed cases (writes redteam/hardening_final/summary.json).

Before: redteam/current_audit/<case>/scores_test.json (iteration-12 hidden test,
REDTEAM.md). After: redteam/hardening_final/<case>/scores_test.json (hardened test).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path("/home/user")
BEFORE = ROOT / "redteam/current_audit"
AFTER = ROOT / "redteam/hardening_final"
HIGHER = {"min_margin"}


def load(path):
    try:
        return json.loads(path.read_text())["experiments"]
    except (OSError, ValueError, KeyError):
        return None


def proposed(scores):
    return {exp: entry["results"]["deviation_rating"] for exp, entry in scores.items()}


def compare(case, ref):
    out = {}
    for exp, metrics in case.items():
        worse = {m: v for m, v in metrics.items()
                 if (v < ref[exp][m] if m in HIGHER else v > ref[exp][m])}
        better = {m: v for m, v in metrics.items()
                  if (v > ref[exp][m] if m in HIGHER else v < ref[exp][m])}
        failed = all(abs(v) >= 1e6 for v in metrics.values())
        out[exp] = "failed" if failed else ("worse" if worse and not better else
                                            "better" if better and not worse else
                                            "mixed" if worse else "ties")
    return out


def main():
    status = json.loads((AFTER / "bundle_status.json").read_text()) if (AFTER / "bundle_status.json").exists() else []
    names = [s["name"] for s in status]
    ref_before = proposed(load(BEFORE / "reference_seed_0/scores_test.json"))
    after_ref_scores = load(AFTER / "reference_seed_0/scores_test.json")
    ref_after = proposed(after_ref_scores) if after_ref_scores else None
    summary = {"reference_before": ref_before, "reference_after": ref_after, "cases": {}}
    for name in names:
        before, after = load(BEFORE / name / "scores_test.json"), load(AFTER / name / "scores_test.json")
        entry = {"before": proposed(before) if before else None, "after": proposed(after) if after else None}
        if before:
            entry["before_vs_reference"] = compare(entry["before"], ref_before)
        if after and ref_after:
            entry["after_vs_reference"] = compare(entry["after"], ref_after)
        summary["cases"][name] = entry
    (AFTER / "summary.json").write_text(json.dumps(summary, indent=2))
    for name, entry in summary["cases"].items():
        print(name, "| before:", entry.get("before_vs_reference"), "| after:", entry.get("after_vs_reference"))


if __name__ == "__main__":
    main()
