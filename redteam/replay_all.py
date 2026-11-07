#!/usr/bin/env python3
"""Replay the reference (2 runs; scripts/run.sh is the third) and every shortcut in redteam/ through the final hidden test.

Each case runs through its own harness (redteam/shortcut_harness.py for the 51
iteration-11 cases, redteam/audit_v2/shortcut_harness.py for the redteam's 11
and the 3 new probes), test only (SHORTCUT_SKIP_TRAIN=1: the train slice is
not part of any hidden score). Evidence goes to redteam/<name>/final/ (the
reference: redteam/reference_runs/run_<k>/final/). Cases already replayed
against the current hidden test (same SHA-256) are skipped, so the driver can
be resumed across jobs; it stops starting new cases after --budget seconds.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

ROOT = Path("/home/user")
OLD = json.loads((ROOT / "redteam/shortcut_cases.json").read_text())
AUDIT = ["zero_gain_fallback_shortcut", "lax_cce_shortcut", "zero_nondominated_shortcut",
         "batch_transport_shortcut", "large_game_abandonment_shortcut", "negative_tolerance_shortcut",
         "tiny_rating_mismatch_shortcut", "bystander_drop_shortcut", "fixed_options_shortcut",
         "score_symlink_shortcut", "prestarted_writer_shortcut"]
NEW = ["strict_batch_transport_shortcut", "memo_transport_shortcut", "sheriff_special_case_shortcut"]


def cases():
    out = [("reference", k) for k in range(2)]  # a third reference run is scripts/run.sh itself
    out += [("old", name) for name in OLD]
    out += [("audit", name) for name in AUDIT + NEW]
    return out


def folder(kind, name):
    if kind == "reference":
        return ROOT / f"redteam/reference_runs/run_{name}/final"
    return ROOT / "redteam" / name / "final"


def done(kind, name, sha):
    status = folder(kind, name) / "status.json"
    if not status.is_file():
        return False
    data = json.loads(status.read_text())
    return sha in (data.get("restored_hidden_sha256"), data.get("hidden_sha256")) and "test" in data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--budget", type=float, default=3000.0)
    parser.add_argument("--only", default="", help="comma-separated case names (reference runs: 'reference')")
    args = parser.parse_args()
    only = set(filter(None, args.only.split(",")))
    sha = hashlib.sha256((ROOT / "eval/test/evaluate.py").read_bytes()).hexdigest()
    start = time.monotonic()
    env = dict(os.environ, SHORTCUT_SKIP_TRAIN="1")
    pending = [c for c in cases() if not done(*c, sha)
               and (not only or c[1] in only or (c[0] == "reference" and "reference" in only))]
    print(f"hidden test sha256 {sha}; {len(pending)} of {len(cases())} cases pending", flush=True)
    for kind, name in pending:
        if time.monotonic() - start > args.budget:
            print("budget reached; resume in the next job", flush=True)
            break
        if kind == "reference":
            command = ["python3", "redteam/shortcut_harness.py", "--reference-run", str(name), "--subdir", "final"]
        elif kind == "old":
            command = ["python3", "redteam/shortcut_harness.py", "--shortcut", name, "--subdir", "final"]
        else:
            command = ["python3", "redteam/audit_v2/shortcut_harness.py", name, "--evidence-subdir", "final"]
        t0 = time.monotonic()
        completed = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=2400)
        scores = folder(kind, name) / "scores_test.json"
        summary = "no scores"
        if scores.is_file():
            data = json.loads(scores.read_text())["experiments"]
            summary = json.dumps({e: v["results"]["deviation_rating"] for e, v in data.items()})
        print(f"[{kind}] {name}: exit {completed.returncode}, {time.monotonic() - t0:.0f} s; {summary}", flush=True)
        if completed.returncode != 0:
            print(completed.stdout[-2000:], completed.stderr[-2000:], flush=True)
    remaining = [c for c in cases() if not done(*c, sha)]
    print(f"{len(remaining)} cases still pending", flush=True)


if __name__ == "__main__":
    main()
