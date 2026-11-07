"""Iteration-13 replays: the reference, honest variants and the fixed shortcuts through the hardened hidden test.

Sequential (the hidden test watches the workspace for file changes during calls),
one exact `bash scripts/evaluate_test.sh` per case via harness.py. A failing case
is recorded and the bundle continues.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

ROOT = Path("/home/user")
HERE = ROOT / "redteam/hardening_final"
CASES = [
    "three_lp_shortcut", "size_abandonment_shortcut", "reference_seed_0", "weaker_one_lp",
    "two_lp_shortcut", "active_freeze_variant", "vectorized_solver", "precision_solver",
    "reference_seed_1",
]
HIDDEN = ROOT / "eval/test/evaluate.py"


def finished(folder: Path) -> bool:
    """A case already replayed against the current hidden test (the bundle resumes across jobs)."""
    try:
        status = json.loads((folder / "status.json").read_text())
    except (OSError, ValueError):
        return False
    import hashlib
    return ((folder / "scores_test.json").is_file() and status.get("test", {}).get("returncode") == 0
            and status.get("hidden_sha256") == hashlib.sha256(HIDDEN.read_bytes()).hexdigest())


def main():
    started = time.monotonic()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
    result = []
    for name in CASES:
        folder = HERE / name
        folder.mkdir(exist_ok=True)
        if finished(folder):
            print(f"SKIP {name}: already replayed against the current hidden test", flush=True)
            result.append({"name": name, "returncode": 0, "skipped": True})
            continue
        print(f"START {name}, elapsed={time.monotonic() - started:.0f}s", flush=True)
        command = ["python3", str(HERE / "harness.py"), name]
        with (folder / "harness.log").open("w") as stream:
            proc = subprocess.run(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
        result.append({"name": name, "returncode": proc.returncode, "elapsed": round(time.monotonic() - started, 1)})
        (HERE / "bundle_status.json").write_text(json.dumps(result, indent=2))
        print(f"END {name}, returncode={proc.returncode}", flush=True)
        if proc.returncode:
            print((folder / "harness.log").read_text()[-3000:], flush=True)
    print("Replay bundle complete", flush=True)


if __name__ == "__main__":
    main()
