"""
Evaluation for stored experiment outputs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict


ROOT = Path("/home/user")
METHOD_DIR = ROOT / "checkpoints" / "method"
BASELINE_DIR = ROOT / "checkpoints" / "baseline"
SCORING_DIR = ROOT / "scoring"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def evaluate_shapley() -> Dict:
    method = _load_json(METHOD_DIR / "biased_shapley_augmented.json")
    baseline = _load_json(BASELINE_DIR / "uniform_biased_shapley.json")
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


def evaluate_clone_invariance() -> Dict:
    payload = _load_json(METHOD_DIR / "clone_invariance.json")
    orig = payload["original"]["ratings"]["0"]
    cloned = payload["cloned"]["ratings"]["0"]
    max_diff = max(abs(cloned[str(i)] - orig[str(i)]) for i in range(3))
    return {
        "max_diff": round(max_diff, 8),
        "original_cce_gap": round(payload["original"]["cce_gap"], 8),
        "cloned_cce_gap": round(payload["cloned"]["cce_gap"], 8),
    }


def evaluate_mixture_invariance() -> Dict:
    payload = _load_json(METHOD_DIR / "mixture_invariance.json")
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


def evaluate_offset_invariance() -> Dict:
    payload = _load_json(METHOD_DIR / "offset_invariance.json")
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


def evaluate_dominance_preserving() -> Dict:
    payload = _load_json(METHOD_DIR / "dominance_preserving.json")
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

    scores = {"experiments": {}}
    shapley = evaluate_shapley()
    scores["experiments"]["biased_shapley_augmented"] = {
        "results": {
            "deviation_rating": {
                "dev_gap": shapley["dev_gap"],
                "CCE_gap": shapley["CCE_gap"],
            },
        }
    }

    clone = evaluate_clone_invariance()
    scores["experiments"]["clone_invariance"] = {
        "results": {
            "deviation_rating": {
                "max_diff": clone["max_diff"],
            }
        }
    }

    mixture = evaluate_mixture_invariance()
    scores["experiments"]["mixture_invariance"] = {
        "results": {
            "deviation_rating": {
                "original_max_diff": mixture["original_max_diff"],
                "mixture_error": mixture["mixture_error"],
            }
        }
    }

    offset = evaluate_offset_invariance()
    scores["experiments"]["offset_invariance"] = {
        "results": {
            "deviation_rating": {
                "max_diff": offset["max_diff"],
            }
        }
    }

    dominance = evaluate_dominance_preserving()
    scores["experiments"]["dominance_preserving"] = {
        "results": {
            "deviation_rating": {
                "dominance_violations": dominance["dominance_violations"],
                "CCE_gap": dominance["CCE_gap"],
            }
        }
    }

    (SCORING_DIR / "scores.json").write_text(json.dumps(scores, indent=2))
    print(json.dumps(scores, indent=2))
    return scores


if __name__ == "__main__":
    main()
