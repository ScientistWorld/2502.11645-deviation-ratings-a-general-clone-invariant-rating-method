#!/usr/bin/env python3
"""Replay one shortcut (or the reference) transactionally through the hidden test.

For a shortcut: install it (scripts/rate.sh plus its workspace edits), run the
visible train evaluation, restore the gym's eval/ tree and
scripts/evaluate_test.sh, run ``bash scripts/evaluate_test.sh`` with no
arguments, keep every output in redteam/<name>/, then restore the workspace.
Outputs of the pre-hardening audit are kept under redteam/<name>/before_hardening/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

ROOT = Path("/home/user")
STATE = ROOT / "redteam/_restore_state"
DIRECTORIES = ["eval", "data", "baseline", "method", "scoring", "checkpoints"]
FILES = ["scripts/evaluate_test.sh", "scripts/rate.sh", "sitecustomize.py"]
OLD_OUTPUTS = ["scores_test.json", "scores_train.json", "test.log", "train.log", "producer.log",
               "status.json", "submitted_artifacts", "installed_files", "initial_shortcut_run"]
MARKERS = ["daemon_rewrote_scores.txt", "appended_command_ran.txt", "startup_hook_ran.txt"]


def remove(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


def snapshot() -> None:
    if STATE.exists():
        raise RuntimeError("Unrestored shortcut state exists; refusing to overwrite backups")
    STATE.mkdir(parents=True)
    for rel in DIRECTORIES + FILES:
        source, target = ROOT / rel, STATE / rel
        if source.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, target, symlinks=True)
            else:
                shutil.copy2(source, target)


def restore_one(rel: str) -> None:
    source, target = STATE / rel, ROOT / rel
    remove(target)
    if source.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target, symlinks=True)
        else:
            shutil.copy2(source, target)


def kill_leftover_shortcut_processes() -> list:
    """Belt and braces: the harness itself kills any surviving shortcut process."""
    killed = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit() or int(entry) == os.getpid():
            continue
        try:
            cmdline = Path(f"/proc/{entry}/cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
        except OSError:
            continue
        if "redteam/shortcut_rater.py" in cmdline:
            try:
                os.kill(int(entry), signal.SIGKILL)
                killed.append(cmdline.strip())
            except OSError:
                pass
    return killed


def restore_all() -> None:
    if STATE.exists():
        for rel in DIRECTORIES + FILES:
            restore_one(rel)
        cache = ROOT / "__pycache__"
        if cache.exists():
            for file in cache.glob("sitecustomize.*.pyc"):
                file.unlink()
            if not list(cache.iterdir()):
                cache.rmdir()
        shutil.rmtree(STATE)


def run(command, output: Path, timeout: int = 1800) -> dict:
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1",
               OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
    start = time.monotonic()
    with output.open("w") as log:
        completed = subprocess.run(command, cwd=ROOT, env=env, stdout=log,
                                   stderr=subprocess.STDOUT, timeout=timeout)
    return {"exit_code": completed.returncode, "seconds": round(time.monotonic() - start, 2)}


def nonfinite(obj, prefix=""):
    found = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            found.extend(nonfinite(value, prefix + "." + key))
    elif isinstance(obj, list):
        for idx, value in enumerate(obj):
            found.extend(nonfinite(value, prefix + f"[{idx}]"))
    elif isinstance(obj, float) and not math.isfinite(obj):
        found.append(prefix)
    return found


def archive_before(folder: Path) -> None:
    """Keep the pre-hardening audit outputs of this shortcut, once."""
    before = folder / "before_hardening"
    if before.exists():
        for name in OLD_OUTPUTS + MARKERS + ["submitted_outputs_train.json"]:
            remove(folder / name)
        return
    present = [name for name in OLD_OUTPUTS if (folder / name).exists()]
    if not present:
        return
    before.mkdir()
    for name in present:
        shutil.move(str(folder / name), str(before / name))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shortcut")
    parser.add_argument("--reference-run", type=int)
    parser.add_argument("--restore", action="store_true")
    parser.add_argument("--subdir", default="", help="write this replay's evidence under redteam/<name>/<subdir>")
    args = parser.parse_args()
    if args.restore:
        restore_all()
        return
    is_reference = args.reference_run is not None
    base = ROOT / "redteam" / (f"reference_runs/run_{args.reference_run}" if is_reference else args.shortcut)
    folder = base / args.subdir if args.subdir else base
    folder.mkdir(parents=True, exist_ok=True)
    if not is_reference and not args.subdir:
        archive_before(folder)
    for marker in MARKERS:
        remove(base / marker)
    phase = base / ".phase"
    status = {"shortcut": args.shortcut, "reference_run": args.reference_run,
              "hidden_command": ["bash", "scripts/evaluate_test.sh"]}
    snapshot()
    try:
        for split in ("train", "test"):
            (ROOT / f"scoring/scores_{split}.json").unlink(missing_ok=True)
        remove(ROOT / "checkpoints")
        (ROOT / "checkpoints").mkdir()
        if not is_reference:
            status["producer"] = run(["python3", "redteam/shortcut_candidate.py", args.shortcut],
                                     folder / "producer.log")
            if status["producer"]["exit_code"] != 0:
                return
        edited = {}
        for rel in FILES + ["data/game_data.py", "baseline/run_uniform.py", "scoring/reference.json"]:
            before, after = STATE / rel, ROOT / rel
            if after.exists() and (not before.exists() or before.read_bytes() != after.read_bytes()):
                target = folder / "installed_files" / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(after, target)
                edited[rel] = hashlib.sha256(after.read_bytes()).hexdigest()
        status["edited_files"] = edited
        phase.write_text("train")
        if os.environ.get("SHORTCUT_SKIP_TRAIN") == "1":
            status["train"] = {"skipped": True}
        else:
            status["train"] = run(["bash", "scripts/evaluate_train.sh"], folder / "train.log")
        path = ROOT / "scoring/scores_train.json"
        if path.exists():
            shutil.copy2(path, folder / "scores_train.json")
        # Exactly the hidden-test finalization: the gym's eval/ and test script
        # come back; every other submission edit stays in place.
        restore_one("eval")
        restore_one("scripts/evaluate_test.sh")
        status["restored_hidden_sha256"] = hashlib.sha256((ROOT / "eval/test/evaluate.py").read_bytes()).hexdigest()
        phase.write_text("test")
        status["test"] = run(["bash", "scripts/evaluate_test.sh"], folder / "test.log")
        if args.shortcut == "detached_rewriter_shortcut":
            time.sleep(5)  # give a surviving daemon every chance to rewrite the score file
        path = ROOT / "scoring/scores_test.json"
        if path.exists():
            shutil.copy2(path, folder / "scores_test.json")
            status["nonfinite_test_fields"] = nonfinite(json.loads(path.read_text()))
        else:
            status["nonfinite_test_fields"] = []
        status["scores_produced"] = path.exists()
        status["attack_markers"] = sorted(m for m in MARKERS if (base / m).exists())
        for marker in MARKERS:
            if (base / marker).exists():
                shutil.move(str(base / marker), str(folder / marker))
    except Exception as error:
        status["harness_error"] = repr(error)
        raise
    finally:
        status["leftover_processes_killed_by_harness"] = kill_leftover_shortcut_processes()
        remove(phase)
        (folder / "status.json").write_text(json.dumps(status, indent=2))
        restore_all()
    print(json.dumps({"shortcut": args.shortcut, "reference_run": args.reference_run,
                      "train": status.get("train", {}).get("exit_code"),
                      "test": status.get("test", {}).get("exit_code"),
                      "markers": status.get("attack_markers")}))


if __name__ == "__main__":
    main()
