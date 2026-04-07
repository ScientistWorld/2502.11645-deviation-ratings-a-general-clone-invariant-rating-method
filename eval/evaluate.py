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


def evaluate_livebench() -> Dict:
    payload = _load_json(METHOD_DIR / "livebench_three_player.json")
    models = payload["models"]
    ratings = payload["ratings"]["0"]
    ordered = sorted(((models[i], ratings[str(i)]) for i in range(len(models))), key=lambda item: item[1], reverse=True)
    top_value = ordered[0][1]
    top_group = [model for model, value in ordered if abs(value - top_value) <= 1e-8]
    expected = {"claude-3-5-sonnet", "gemini-1.5-pro", "Llama-3.1-405B", "gpt-4o"}
    return {
        "top_group": top_group,
        "top4_overlap": len(expected.intersection(top_group)),
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

    livebench_path = METHOD_DIR / "livebench_three_player.json"
    if livebench_path.exists():
        livebench = evaluate_livebench()
        scores["experiments"]["llm_rating_livebench"] = {
            "results": {
                "deviation_rating": {
                    "top4_overlap": livebench["top4_overlap"],
                    "CCE_gap": livebench["CCE_gap"],
                }
            }
        }

    (SCORING_DIR / "scores.json").write_text(json.dumps(scores, indent=2))
    print(json.dumps(scores, indent=2))
    return scores


if __name__ == "__main__":
    main()
