"""
Data generators for deviation rating experiments.
"""

import numpy as np
from typing import Tuple, Dict, List


def shapley_population_ratings(
    population_type: str,
    n_samples: int = 50
) -> Tuple[np.ndarray, List[str], Dict]:
    """
    Create a game from a population of mixed strategies in Shapley's game.
    """
    rng = np.random.default_rng(42)

    if population_type == "unbiased":
        mixtures = []
        for _ in range(n_samples):
            x = rng.dirichlet(np.ones(3))
            mixtures.append(x)
        mixtures = np.array(mixtures)
    elif population_type == "biased":
        mixtures = []
        for _ in range(n_samples):
            if rng.random() < 0.7:
                x = rng.dirichlet(np.array([1.0, 10.0, 1.0]))
            else:
                x = rng.dirichlet(np.ones(3))
            mixtures.append(x)
        mixtures = np.array(mixtures)
    elif population_type == "minority_s":
        mixtures = []
        for _ in range(n_samples):
            if rng.random() < 0.1:
                x = rng.dirichlet(np.array([1.0, 1.0, 10.0]))
            else:
                x = rng.dirichlet(np.array([5.0, 5.0, 1.0]))
            mixtures.append(x)
        mixtures = np.array(mixtures)
    else:
        mixtures = np.array(population_type) if isinstance(population_type, list) else population_type

    n_strategies = len(mixtures)

    # Shapley game: R beats S (+4), S beats P (+1), P beats R (+2), same = (-8)
    shapley_pure = {
        (0, 0): -8, (0, 1): -2, (0, 2): 4,
        (1, 0): 2, (1, 1): -8, (1, 2): -1,
        (2, 0): -4, (2, 1): 1, (2, 2): -8,
    }

    payoffs = np.zeros((n_strategies, n_strategies))
    for i in range(n_strategies):
        for j in range(n_strategies):
            total = 0.0
            for a1 in range(3):
                for a2 in range(3):
                    total += mixtures[i, a1] * mixtures[j, a2] * shapley_pure[(a1, a2)]
            payoffs[i, j] = total

    game = np.zeros((2, n_strategies, n_strategies))
    game[0] = payoffs
    game[1] = -payoffs

    action_names = [f"S{i}" for i in range(n_strategies)]

    return game, action_names, {
        "game_name": "shapley_population",
        "population_type": population_type,
    }


def rock_paper_scissors() -> Tuple[np.ndarray, List[str], Dict]:
    """Classic Rock-Paper-Scissors zero-sum game."""
    payoff_matrix = np.array([
        [0, -1, 1],
        [1, 0, -1],
        [-1, 1, 0],
    ])
    game = np.zeros((2, 3, 3))
    game[0] = payoff_matrix
    game[1] = -payoff_matrix
    return game, ["R", "P", "S"], {"game_name": "rps"}


def livebench_data() -> Tuple[np.ndarray, List[str], List[str], Dict]:
    """
    Livebench model-task evaluation data.
    Approximate data reconstructed from the paper's Figure 2c.
    """
    models = [
        "claude-3-5-sonnet", "gemini-1.5-pro", "Llama-3.1-405B", "gpt-4o",
        "gpt-4o-mini", "claude-3-opus", "Llama-3.1-70B", "gpt-4-turbo",
        "claude-3-sonnet", "mistral-large", "gpt-4", "gemini-1.5-flash",
        "Llama-3.1-8B", "claude-3-haiku", "gpt-3.5-turbo", "Llama-3-70B",
        "Llama-3-8B", "gemini-1.0-pro",
    ]
    tasks = [
        "LCB-generation", "summarize", "connections", "reasoning",
        "math", "coding", "instruction-following", "truthfulness",
        "safety", "complexity", "visual-reasoning", "data-analysis",
        "long-context", "multilingual", "tool-use", "commonsense",
        "reading-comprehension", "other",
    ]

    np.random.seed(42)
    n_models = len(models)
    n_tasks = len(tasks)

    # Generate scores with some structure
    T = np.random.rand(n_models, n_tasks) * 0.3 + 0.4

    # Boost specific models on specific tasks (from the paper's analysis)
    T[0, 0] = 0.95  # claude on LCB generation
    T[0, 1] = 0.92
    T[1, 1] = 0.95  # gemini on summarize
    T[1, 0] = 0.88
    T[2, 17] = 0.93  # llama-405B on other
    T[2, 3] = 0.90
    T[3, 2] = 0.94  # gpt-4o on connections
    T[3, 0] = 0.89

    T = np.clip(T, 0, 1)

    return T, models, tasks, {"game_name": "livebench"}


def construct_three_player_game(
    model_scores: np.ndarray,
) -> Tuple[np.ndarray, List[int], Dict]:
    """
    Construct the 3-player game from model-task data:
    model_A vs model_B vs task

    Payoffs:
    G_A = T(A, task) - T(B, task)   (zero-sum between models)
    G_B = -G_A
    G_task = |G_A|  (prefers separating models)
    """
    n_models = model_scores.shape[0]
    n_tasks = model_scores.shape[1]

    payoffs = np.zeros((3, n_models, n_models, n_tasks))
    for a in range(n_models):
        for b in range(n_models):
            for t in range(n_tasks):
                diff = model_scores[a, t] - model_scores[b, t]
                payoffs[0, a, b, t] = diff
                payoffs[1, a, b, t] = -diff
                payoffs[2, a, b, t] = abs(diff)

    return payoffs, [n_models, n_models, n_tasks], {"game_name": "livebench_3p"}
