# Experiment Overview

## biased_shapley_augmented

Tests whether a method handles a cyclic general-sum game with an added mixed action without forcing an artificial linear ordering.

Scored outputs:
- `dev_gap`: spread between the highest and lowest ratings across `R`, `P`, `S`, and `N`
- `CCE_gap`: equilibrium-feasibility sanity check for the selected recommendation distribution

## clone_invariance

Tests whether duplicating an existing strategy leaves the ratings of the original strategies unchanged.

Scored output:
- `max_diff`: maximum absolute change in any original strategy's rating after cloning
