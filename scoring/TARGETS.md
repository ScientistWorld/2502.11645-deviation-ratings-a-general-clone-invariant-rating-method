# Evaluation Targets

## biased_shapley_augmented

Tests whether the benchmark method collapses the augmented biased Shapley game to a single top group instead of inventing a strict ranking.
- **Metric**: `dev_gap` = max minus min deviation rating over the four player-0 strategies. Lower is better; 0 is perfect equality.
- **Metric**: `CCE_gap` = CCE regret gap of the selected distribution. Lower is better; 0 means exact CCE.

## clone_invariance

Tests whether the method is insensitive to a duplicated strategy in a simple zero-sum game.
- **Metric**: `max_diff` = maximum absolute change in any original rating after cloning one strategy. Lower is better; 0 is perfect invariance.
