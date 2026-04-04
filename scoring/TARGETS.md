# Evaluation Targets

## Primary: deviation_rating_quality

**Biased Shapley Game** — deviation ratings should be equal across all strategies.
- **Metric**: `dev_gap` = max(all ratings) - min(all ratings) for player 0 (lower is better, 0 = perfect equality)
- **Metric**: `CCE_gap` = sum_p max_a' delta_p(a') (lower is better, 0 = exact CCE)
- **Run**: Compute deviation rating on the 4x4 biased Shapley game

**Livebench** — deviation ratings should group the top 4 models equally at the top.
- **Metric**: `top4_overlap` = number of expected top-4 models in the top group (higher is better, max = 4)
- **Run**: Construct 3-player game from model-task scores, compute deviation ratings

## Constraint: clone_invariance

Adding a copy of a strategy must not change existing ratings.
- **Metric**: `max_diff` = max absolute change in any original rating after adding a clone (lower is better, 0 = perfect invariance)
- **Run**: Compare ratings before/after adding a strategy clone to Rock-Paper-Scissors

## Secondary: uniform_baseline

Uniform averaging as a baseline comparison.
- The scientist should verify that uniform rating gives a different (transitive) ranking compared to deviation rating, demonstrating the value of game-theoretic equilibrium-based ratings.
