# Evaluation Targets

## biased_shapley_augmented

Tests the paper's Table 2 phenomenon: the biased Shapley game with the added Nash strategy should collapse to a single top group under deviation rating.
- **Metric**: `dev_gap` = max minus min deviation rating over the four player-0 strategies. Lower is better; 0 is perfect equality.
- **Metric**: `CCE_gap` = CCE regret gap of the selected distribution. Lower is better; 0 means exact CCE.

## clone_invariance

Tests the paper's clone-invariance claim on a simple zero-sum game.
- **Metric**: `max_diff` = maximum absolute change in any original rating after cloning one strategy. Lower is better; 0 is perfect invariance.
