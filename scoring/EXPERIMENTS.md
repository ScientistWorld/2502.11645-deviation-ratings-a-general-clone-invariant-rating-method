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

## mixture_invariance

Tests whether adding a mixed strategy leaves the original strategies' ratings unchanged and gives the new strategy the corresponding mixed rating.

Scored outputs:
- `original_max_diff`: maximum absolute change in any original strategy's rating after adding the mixed strategy
- `mixture_error`: absolute error between the mixed strategy's rating and the expected mixture of the original ratings

## offset_invariance

Tests whether adding offsets that depend only on the opponents' actions leaves ratings unchanged.

Scored output:
- `max_diff`: maximum absolute change in any strategy's rating before versus after the offset transformation

## dominance_preserving

Tests whether a dominant strategy is never rated below a dominated strategy on a small game with encoded dominance relations.

Scored outputs:
- `dominance_violations`: number of violated dominance relations
- `CCE_gap`: equilibrium-feasibility sanity check for the selected recommendation distribution
