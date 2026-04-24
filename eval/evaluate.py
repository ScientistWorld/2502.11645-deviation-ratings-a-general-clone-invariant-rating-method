"""Evaluate stored experiment outputs for all discovered methods."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

from eval.split_common import SCORING_DIR, _read_json, discover_method_dirs


ROOT = Path("/home/user")
BASELINE_DIR = ROOT / "checkpoints" / "baseline"


def evaluate_shapley(method_dir: Path) -> Dict:
    method = _read_json(method_dir / "biased_shapley_augmented.json")
    baseline = _read_json(BASELINE_DIR / "uniform_biased_shapley.json")
    names = method["action_names"]

    dev_values = [method["ratings"]["0"][str(i)] for i in range(len(names))]
    uniform_values = [baseline["ratings"]["0"][str(i)] for i in range(len(names))]
    dev_gap = max(dev_values) - min(dev_values)

    uniform_rank = [name for _, name in sorted(zip(uniform_values, names), reverse=True)]
    return {
        "deviation_ratings": {name: round(value, 6) for name, value in zip(names, dev_values)},
        "uniform_ratings": {name: round(value, 6) for name, value in zip(names, uniform_values)},
        "uniform_ranking": uniform_rank,
        "uniform_order_matches_paper": uniform_rank == ["R", "P", "N", "S"],
        "dev_gap": round(dev_gap, 8),
        "CCE_gap": round(method["cce_gap"], 8),
    }


def evaluate_clone_invariance(method_dir: Path) -> Dict:
    payload = _read_json(method_dir / "clone_invariance.json")
    orig = payload["original"]["ratings"]["0"]
    cloned = payload["cloned"]["ratings"]["0"]
    max_diff = max(abs(cloned[str(i)] - orig[str(i)]) for i in range(3))
    return {
        "max_diff": round(max_diff, 8),
        "original_cce_gap": round(payload["original"]["cce_gap"], 8),
        "cloned_cce_gap": round(payload["cloned"]["cce_gap"], 8),
    }


def evaluate_mixture_invariance(method_dir: Path) -> Dict:
    payload = _read_json(method_dir / "mixture_invariance.json")
    base = payload["base"]["ratings"]
    augmented = payload["augmented"]["ratings"]

    diffs = []
    for player, max_action in (("0", 2), ("1", 2)):
        for action in range(max_action):
            diffs.append(abs(augmented[player][str(action)] - base[player][str(action)]))

    mixture_error = abs(augmented["0"]["2"] - payload["expected_mixture_rating"])
    return {
        "original_max_diff": round(max(diffs), 8),
        "mixture_error": round(mixture_error, 8),
        "base_CCE_gap": round(payload["base"]["cce_gap"], 8),
        "augmented_CCE_gap": round(payload["augmented"]["cce_gap"], 8),
    }


def evaluate_offset_invariance(method_dir: Path) -> Dict:
    payload = _read_json(method_dir / "offset_invariance.json")
    base = payload["base"]["ratings"]
    offset = payload["offset"]["ratings"]

    diffs = []
    for player in ("0", "1"):
        for action in ("0", "1"):
            diffs.append(abs(offset[player][action] - base[player][action]))

    return {
        "max_diff": round(max(diffs), 8),
        "base_CCE_gap": round(payload["base"]["cce_gap"], 8),
        "offset_CCE_gap": round(payload["offset"]["cce_gap"], 8),
    }


def evaluate_dominance_preserving(method_dir: Path) -> Dict:
    payload = _read_json(method_dir / "dominance_preserving.json")
    ratings = payload["ratings"]

    margins = []
    violations = 0
    for pair in payload["dominance_pairs"]:
        player = str(pair["player"])
        better = str(pair["better"])
        worse = str(pair["worse"])
        margin = ratings[player][better] - ratings[player][worse]
        margins.append(margin)
        if margin < -1e-8:
            violations += 1

    return {
        "dominance_violations": violations,
        "min_margin": round(min(margins), 8),
        "CCE_gap": round(payload["cce_gap"], 8),
    }


def main() -> Dict:
    SCORING_DIR.mkdir(parents=True, exist_ok=True)

    method_dirs = discover_method_dirs()
    scores = {"experiments": {}}
    scores["experiments"]["biased_shapley_augmented"] = {
        "results": {}
    }
    for method_id, method_dir in method_dirs.items():
        shapley = evaluate_shapley(method_dir)
        scores["experiments"]["biased_shapley_augmented"]["results"][method_id] = {
            "dev_gap": shapley["dev_gap"],
            "CCE_gap": shapley["CCE_gap"],
        }

    scores["experiments"]["clone_invariance"] = {
        "results": {}
    }
    for method_id, method_dir in method_dirs.items():
        clone = evaluate_clone_invariance(method_dir)
        scores["experiments"]["clone_invariance"]["results"][method_id] = {
            "max_diff": clone["max_diff"],
        }

    scores["experiments"]["mixture_invariance"] = {
        "results": {}
    }
    for method_id, method_dir in method_dirs.items():
        mixture = evaluate_mixture_invariance(method_dir)
        scores["experiments"]["mixture_invariance"]["results"][method_id] = {
            "original_max_diff": mixture["original_max_diff"],
            "mixture_error": mixture["mixture_error"],
        }

    scores["experiments"]["offset_invariance"] = {
        "results": {}
    }
    for method_id, method_dir in method_dirs.items():
        offset = evaluate_offset_invariance(method_dir)
        scores["experiments"]["offset_invariance"]["results"][method_id] = {
            "max_diff": offset["max_diff"],
        }

    scores["experiments"]["dominance_preserving"] = {
        "results": {}
    }
    for method_id, method_dir in method_dirs.items():
        dominance = evaluate_dominance_preserving(method_dir)
        scores["experiments"]["dominance_preserving"]["results"][method_id] = {
            "dominance_violations": dominance["dominance_violations"],
            "CCE_gap": dominance["CCE_gap"],
        }

    (SCORING_DIR / "scores.json").write_text(json.dumps(scores, indent=2))
    print(json.dumps(scores, indent=2))
    return scores


if __name__ == "__main__":
    main()
