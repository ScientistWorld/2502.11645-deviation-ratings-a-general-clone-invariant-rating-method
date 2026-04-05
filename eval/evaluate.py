"""
Evaluation code for deviation rating experiments.
"""

import numpy as np
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'method'))

from deviation_rating import (
    deviation_rating, uniform_rating, cce_gap,
    biased_shapley_game, standard_shapley_game
)
from game_generators import (
    rock_paper_scissors,
    livebench_data, construct_three_player_game,
    shapley_population_ratings
)


def evaluate_shapley_game() -> Dict:
    """Biased Shapley game: deviation rating should give equal ratings."""
    payoffs, action_names, meta = biased_shapley_game()

    uni = uniform_rating(payoffs, 2, [3, 3])
    dev = deviation_rating(payoffs, 2, [3, 3], verbose=False)
    gap = cce_gap(payoffs, dev["equilibrium"], 2, [3, 3])

    dev_vals = [dev["ratings_dict"][0][i] for i in range(3)]
    dev_gap = max(dev_vals) - min(dev_vals)
    all_equal = dev_gap < 0.01

    def rank(ratings_dict, player=0):
        items = sorted(ratings_dict[player].items(), key=lambda x: x[1], reverse=True)
        return [(action_names[i], round(v, 4)) for i, v in items]

    return {
        "uniform_ratings": {action_names[i]: round(uni[0][i], 4) for i in range(3)},
        "deviation_ratings": {action_names[i]: round(dev["ratings_dict"][0][i], 4) for i in range(3)},
        "uniform_ranking": rank(uni),
        "deviation_ranking": rank(dev["ratings_dict"]),
        "all_equal": all_equal,
        "dev_gap": round(dev_gap, 6),
        "CCE_gap": round(gap, 6),
        "n_iterations": dev["n_iterations"],
    }


def evaluate_clone_invariance() -> Dict:
    """Test clone invariance on Rock-Paper-Scissors."""
    payoffs, action_names, meta = rock_paper_scissors()

    # Original RPS
    orig = deviation_rating(payoffs, 2, [3, 3], verbose=False)

    # Clone: player 0 has 4 actions (R,P,S + clone of R)
    clone_payoffs = np.zeros((2, 4, 3))
    clone_payoffs[:, :3, :] = payoffs
    clone_payoffs[:, 3, :] = payoffs[:, 0, :]

    cloned = deviation_rating(clone_payoffs, 2, [4, 3], verbose=False)

    max_diff = 0.0
    for a in range(3):
        diff = abs(cloned["ratings_dict"][0][a] - orig["ratings_dict"][0][a])
        if diff > max_diff:
            max_diff = diff

    return {
        "clone_invariant": max_diff < 0.01,
        "max_diff": round(max_diff, 8),
        "orig": {action_names[i]: round(orig["ratings_dict"][0][i], 6) for i in range(3)},
        "cloned": {str(i): round(cloned["ratings_dict"][0][i], 6) for i in range(4)},
    }


def evaluate_llm_rating() -> Dict:
    """Livebench: deviation rating should group top 4 models at the top."""
    T, models, tasks, meta = livebench_data()
    game, action_dims, _ = construct_three_player_game(T)

    dev = deviation_rating(game, 3, action_dims, verbose=False)
    gap = cce_gap(game, dev["equilibrium"], 3, action_dims)

    ratings = {models[i]: round(dev["ratings_dict"][0][i], 6) for i in range(len(models))}
    sorted_models = sorted(ratings.items(), key=lambda x: x[1], reverse=True)

    top_r = sorted_models[0][1]
    top_group = [m for m, r in sorted_models if abs(r - top_r) < 0.01]

    expected = {"claude-3-5-sonnet", "gemini-1.5-pro", "Llama-3.1-405B", "gpt-4o"}
    overlap = len(expected.intersection(set(top_group)))

    return {
        "sorted_models": [(m, round(r, 6)) for m, r in sorted_models[:8]],
        "top_group": top_group,
        "top4_overlap": overlap,
        "CCE_gap": round(gap, 6),
    }


def evaluate_population_study() -> Dict:
    """Population ratings: deviation should give equal ratings regardless of distribution."""
    results = {}
    for pt in ["unbiased", "biased"]:
        game, names, _ = shapley_population_ratings(pt, n_samples=15)
        n = game.shape[1]
        dev = deviation_rating(game, 2, [n, n], verbose=False)
        vals = list(dev["ratings_dict"][0].values())
        results[pt] = {
            "dev_spread": round(max(vals) - min(vals), 6),
            "all_equal": (max(vals) - min(vals)) < 0.01,
        }
    return results


def main():
    os.makedirs("/home/user/scoring", exist_ok=True)

    print("=" * 60)
    print("EVALUATION: Deviation Rating Reproduction")
    print("=" * 60)

    print("\n[1] Biased Shapley Game...")
    shapley = evaluate_shapley_game()
    print(f"  Dev ratings: {shapley['deviation_ratings']}")
    print(f"  All equal: {shapley['all_equal']}, gap: {shapley['dev_gap']}, CCE: {shapley['CCE_gap']}")
    print(f"  Dev rank: {shapley['deviation_ranking']}")
    print(f"  Uni rank:  {shapley['uniform_ranking']}")

    print("\n[2] Clone Invariance...")
    clone = evaluate_clone_invariance()
    print(f"  Clone invariant: {clone['clone_invariant']}, max_diff: {clone['max_diff']}")

    print("\n[3] LLM Rating (Livebench)...")
    llm = evaluate_llm_rating()
    print(f"  Top4 overlap: {llm['top4_overlap']}/4, CCE gap: {llm['CCE_gap']}")
    print(f"  Top group ({len(llm['top_group'])}): {llm['top_group'][:6]}...")

    print("\n[4] Population Study...")
    pop = evaluate_population_study()
    for pt, d in pop.items():
        print(f"  {pt}: spread={d['dev_spread']}, equal={d['all_equal']}")

    # Build scores.json matching reference.json structure
    scores = {
        "experiments": {
            "biased_shapley_game": {
                "results": {
                    "deviation_rating": {
                        "dev_gap": shapley["dev_gap"],
                        "CCE_gap": shapley["CCE_gap"],
                    },
                },
            },
            "clone_invariance": {
                "results": {
                    "deviation_rating": {
                        "max_diff": clone["max_diff"],
                    },
                },
            },
            "llm_rating_livebench": {
                "results": {
                    "deviation_rating": {
                        "top4_overlap": llm["top4_overlap"],
                        "CCE_gap": llm["CCE_gap"],
                    },
                },
            },
        }
    }

    with open("/home/user/scoring/scores.json", "w") as f:
        json.dump(scores, f, indent=2)

    print("\nResults written to scoring/scores.json")
    return scores


if __name__ == "__main__":
    main()
