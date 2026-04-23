#!/usr/bin/env python3
"""
Shared helpers for split evaluation.
"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path("/home/user")
CHECKPOINTS_DIR = ROOT / "checkpoints"
SCORING_DIR = ROOT / "scoring"
REQUIRED_ARTIFACTS = (
    "biased_shapley_augmented.json",
    "clone_invariance.json",
    "mixture_invariance.json",
    "offset_invariance.json",
    "dominance_preserving.json",
)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _expected_method_ids() -> list[str]:
    reference_path = SCORING_DIR / "reference.json"
    if not reference_path.exists():
        return []

    reference = _read_json(reference_path)
    method_ids: set[str] = set()
    for experiment in reference.get("experiments", {}).values():
        method_ids.update(experiment.get("results", {}).keys())
    return sorted(method_ids)


def _has_required_artifacts(path: Path) -> bool:
    return path.is_dir() and all((path / name).exists() for name in REQUIRED_ARTIFACTS)


def discover_method_dirs() -> dict[str, Path]:
    """
    Discover scored method outputs.

    Supported layouts:
    - Legacy single-method layout: checkpoints/method/*.json
    - Multi-method layout: checkpoints/outputs/<method_id>/*.json
    - Flat multi-method layout: checkpoints/<method_id>/*.json
    """

    discovered: dict[str, Path] = {}

    outputs_dir = CHECKPOINTS_DIR / "outputs"
    if outputs_dir.is_dir():
        for child in sorted(outputs_dir.iterdir()):
            if _has_required_artifacts(child):
                discovered[child.name] = child

    expected_method_ids = _expected_method_ids()
    legacy_method_id = expected_method_ids[0] if len(expected_method_ids) == 1 else "method"

    for child in sorted(CHECKPOINTS_DIR.iterdir()):
        if child.name in {"baseline", "outputs"}:
            continue
        if not _has_required_artifacts(child):
            continue

        method_id = legacy_method_id if child.name == "method" else child.name
        discovered.setdefault(method_id, child)

    if not discovered:
        checked = [
            str(CHECKPOINTS_DIR / "method"),
            str(CHECKPOINTS_DIR / "outputs"),
        ]
        raise FileNotFoundError(
            "No scored method artifacts found. Expected one of: "
            + ", ".join(checked)
        )

    return discovered
