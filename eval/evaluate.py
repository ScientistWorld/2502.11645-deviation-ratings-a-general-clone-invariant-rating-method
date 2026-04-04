"""
Evaluation code for deviation rating experiments.
"""

import numpy as np
import json
import sys
import os
from typing import Dict, Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'method'))

from deviation_rating import (
    deviation_rating, uniform_rating, cce_gap,
    biased_shapley_game
)
from game_generators import (
    rock_paper_scissors,
    livebench_data, construct_three_player_game,
    shapley_population_ratings
)


def evaluate_shapley_game() -> Dict[str, Any]:
    """
    Evaluate on the biased Shapley game (Section 5.1 of the paper).

    Paper claims:
    - Uniform rating: transitive ranking R > P > N > S
    - Deviation rating: equal ratings R = P = S = N
    """
    payoffs, action_names, meta = biased_shapley_game()

    # Uniform rating
    uni_ratings = uniform_rating(payoffs, 2, [4, 4])

    # Deviation rating
    dev_result = deviation_rating(payoffs, 2, [4, 4], verbose=False)
    dev_ratings = dev_result["ratings_dict"]

    # Compute rankings
    def get_ranking(ratings_dict, player=0):
        items = sorted(ratings_dict[player].items(), key=lambda x: x[1], reverse=True)
        return [(action_names[i], round(v, 4)) for i, v in items]

    uni_rank = get_ranking(uni_ratings, 0)
    dev_rank = get_ranking(dev_ratings, 0)

    # Check: deviation ratings should be equal (within tolerance)
    dev_values = [dev_ratings[0][i] for i in range(4)]
    dev_equal = max(dev_values) - min(dev_values) < 0.1

    # CCE gap should be 0 (exact equilibrium)
    gap = cce_gap(payoffs, dev_result["equilibrium"], 2, [4, 4])

    return {
        "uniform_ratings": {action_names[i]: round(uni_ratings[0][i], 4) for i in range(4)},
        "deviation_ratings": {action_names[i]: round(dev_ratings[0][i], 4) for i in range(4)},
        "uniform_ranking": uni_rank,
        "deviation_ranking": dev_rank,
        "all_equal": dev_equal,
        "deviation_gap": max(dev_values) - min(dev_values),
        "CCE_gap": round(gap, 6),
        "n_iterations": dev_result["n_iterations"],
        "equilibrium": dev_result["equilibrium"],
    }


def evaluate_clone_invariance() -> Dict[str, Any]:
    """
    Test clone invariance: adding a copy of a strategy should not change ratings.
    """
    payoffs, action_names, meta = rock_paper_scissors()

    # Original game (RPS)
    result_orig = deviation_rating(payoffs, 2, [3, 3], verbose=False)
    ratings_orig = result_orig["ratings_dict"]

    # Clone game: player 1 has 4 actions (R,P,S + clone of R), player 2 has 3
    payoffs_clone = np.zeros((2, 4, 3))
    payoffs_clone[:, :3, :] = payoffs
    payoffs_clone[:, 3, :] = payoffs[:, 0, :]  # clone of R

    result_clone = deviation_rating(payoffs_clone, 2, [4, 3], verbose=False)
    ratings_clone = result_clone["ratings_dict"]

    # Check: original R, P, S for player 1 should be unchanged
    max_diff = 0.0
    for a in range(3):
        diff = abs(ratings_clone[0][a] - ratings_orig[0][a])
        if diff > max_diff:
            max_diff = diff

    clone_invariant = max_diff < 0.01

    return {
        "original_ratings": {action_names[i]: round(ratings_orig[0][i], 6) for i in range(3)},
        "clone_ratings_p0": {str(i): round(ratings_clone[0][i], 6) for i in range(4)},
        "clone_invariant": clone_invariant,
        "max_diff": round(max_diff, 8),
    }


def evaluate_llm_rating() -> Dict[str, Any]:
    """
    Evaluate on Livebench data (Section 5.2 of the paper).

    Paper claims: deviation rating groups top 4 models equally at the top.
    """
    T, models, tasks, meta = livebench_data()
    game, action_dims, game_meta = construct_three_player_game(T)

    # Deviation rating on the 3-player game
    result = deviation_rating(game, 3, action_dims, verbose=False)
    dev_ratings = result["ratings_dict"]

    # Model A's ratings (player 0)
    model_ratings = {models[i]: round(dev_ratings[0][i], 6) for i in range(len(models))}

    # Sort by rating
    sorted_models = sorted(model_ratings.items(), key=lambda x: x[1], reverse=True)

    # Top group
    if sorted_models:
        top_rating = sorted_models[0][1]
        top_group = [m for m, r in sorted_models if abs(r - top_rating) < 0.01]
        expected_top = {"claude-3-5-sonnet", "gemini-1.5-pro", "Llama-3.1-405B", "gpt-4o"}
        top4_overlap = len(expected_top.intersection(set(top_group)))
    else:
        top_group = []
        top4_overlap = 0

    gap = cce_gap(game, result["equilibrium"], 3, action_dims)

    return {
        "model_ratings": model_ratings,
        "sorted_models": [(m, round(r, 6)) for m, r in sorted_models[:8]],
        "top_group": top_group,
        "top4_overlap": top4_overlap,
        "CCE_gap": round(gap, 6),
        "n_iterations": result["n_iterations"],
    }


def evaluate_population_study() -> Dict[str, Any]:
    """Population ratings from Section 5.1."""
    results = {}
    for pop_type in ["unbiased", "biased"]:
        game, action_names, meta = shapley_population_ratings(pop_type, n_samples=20)
        n = game.shape[1]

        uni = uniform_rating(game, 2, [n, n])
        dev = deviation_rating(game, 2, [n, n], verbose=False)

        dev_vals = list(dev["ratings_dict"][0].values())
        dev_range = max(dev_vals) - min(dev_vals)

        results[pop_type] = {
            "uniform_spread": round(max(uni[0].values()) - min(uni[0].values()), 6),
            "deviation_spread": round(dev_range, 6),
            "all_dev_equal": dev_range < 0.01,
        }

    return results


def main():
    """Run all evaluations and write scoring/scores.json."""
    os.makedirs("/home/user/scoring", exist_ok=True)

    print("=" * 60)
    print("EVALUATION: Deviation Rating Reproduction")
    print("=" * 60)

    print("\n[1] Biased Shapley Game...")
    shapley = evaluate_shapley_game()
    print(f"  Dev ratings: {shapley['deviation_ratings']}")
    print(f"  All equal: {shapley['all_equal']}, CCE gap: {shapley['CCE_gap']}")
    print(f"  Dev ranking: {shapley['deviation_ranking']}")
    print(f"  Uni ranking:  {shapley['uniform_ranking']}")

    print("\n[2] Clone Invariance...")
    clone = evaluate_clone_invariance()
    print(f"  Clone invariant: {clone['clone_invariant']}")
    print(f"  Max diff: {clone['max_diff']}")

    print("\n[3] LLM Rating (Livebench)...")
    llm = evaluate_llm_rating()
    print(f"  Top 4 overlap: {llm['top4_overlap']}/4")
    print(f"  Top group: {llm['top_group']}")
    print(f"  Top models: {llm['sorted_models'][:5]}")

    print("\n[4] Population Study...")
    pop = evaluate_population_study()
    for pt, data in pop.items():
        print(f"  {pt}: dev spread={data['deviation_spread']}, equal={data['all_dev_equal']}")

    # Build scores.json
    scores = {
        "experiments": {
            "biased_shapley_game": {
                "description": "Biased Shapley game — deviation rating should give equal ratings to all strategies",
                "results": {
                    "deviation_rating": {
                        "type": "proposed",
                        "dev_gap": round(shapley["deviation_gap"], 6),
                        "CCE_gap": shapley["CCE_gap"],
                    },
                    "uniform_rating": {
                        "type": "baseline",
                        "dev_gap": round(max(shapley["uniform_ratings"].values()) - min(shapley["uniform_ratings"].values()), 4),
                    },
                },
            },
            "clone_invariance": {
                "description": "Clone invariance — adding a strategy copy should not change other ratings",
                "results": {
                    "deviation_rating": {
                        "type": "proposed",
                        "max_diff": clone["max_diff"],
                    },
                },
            },
            "llm_rating_livebench": {
                "description": "Livebench LLM rating — deviation rating should group top 4 models equally",
                "results": {
                    "deviation_rating": {
                        "type": "proposed",
                        "top4_overlap": llm["top4_overlap"],
                        "CCE_gap": llm["CCE_gap"],
                    },
                },
            },
        }
    }

    with open("/home/user/scoring/scores.json", "w") as f:
        json.dump(scores, f, indent=2)

    print("\n" + "=" * 60)
    print("Results written to scoring/scores.json")
    print("=" * 60)

    return scores


if __name__ == "__main__":
    main()
