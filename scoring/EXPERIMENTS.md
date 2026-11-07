# Experiment Overview

Every experiment runs the rating program `scripts/rate.sh` on games supplied by the evaluator. The visible evaluators use the five documented public games. The hidden test uses about 190 games that it generates when it runs: 2- and 3-player games, some with a bystander player whose payoff depends only on its own action. Each metric below is the maximum over the experiment's games (dominance violations are summed). Outputs must pass the validity gates in [TARGETS.md](/home/user/scoring/TARGETS.md), or the experiment is scored as failed.

## biased_shapley_augmented

Tests whether a method rates cyclic games without forcing an artificial linear order. Public game: paper Table 2 (biased Shapley game plus its Nash mixture N). Hidden games: relabeled, scaled, offset, cloned and populated variants, and versions with a bystander player, plus zero-sum RPS, weighted RPS and RPS-lizard-Spock. In all of them the deviation ratings are provably equal.

Scored outputs:
- `dev_gap`: spread of the first cyclic player's ratings
- `CCE_gap`: recomputed total CCE regret of the submitted distribution
- `all_player_dev_gap`: spread across both cyclic players' actions
- `player_symmetry_gap`: mismatch between the two players' ratings of the same strategy

## clone_invariance

Tests whether duplicating a strategy leaves the original ratings unchanged. Public game: rock-paper-scissors with player 1's rock cloned. Hidden games: random games with one action cloned at a random position, with all actions relabeled.

Scored outputs:
- `max_diff`: change in the ratings of the other players' strategies, the ones that face the clone
- `all_players_max_diff`: change over all original actions of all players
- `clone_source_gap`: absolute difference between the clone's rating and its source action's

## mixture_invariance

Tests whether adding a mixed strategy (weights fixed by the evaluator) leaves the original ratings unchanged and gives the new strategy the corresponding mixed rating. Public game: the general-sum reference game with a `[0.3, 0.7]` mixture for player 0.

Scored outputs:
- `original_max_diff`: largest change in any original rating (all players)
- `mixture_error`: absolute error between the mixed strategy's rating and the mixture of the original ratings
- `max_CCE_gap`: worst recomputed CCE regret of the base and augmented games

## offset_invariance

Tests whether adding offsets that depend only on the opponents' actions leaves ratings unchanged. Public game: offsets `[[10, -4], [7, -3]]` on the general-sum reference game.

Scored outputs:
- `max_diff`: largest absolute (uncentered) change of any rating
- `max_CCE_gap`: worst recomputed CCE regret of the base and offset-transformed games

## dominance_preserving

Tests whether a strictly dominant strategy is rated above the strategy it dominates. The evaluator computes the dominance pairs from each game. Every game has at least one pair with a constant payoff gap.

Scored outputs:
- `dominance_violations`: number of dominance pairs whose rating advantage is not positive
- `CCE_gap`: recomputed total CCE regret of the submitted distribution
- `min_margin`: smallest ratio of rating advantage to guaranteed payoff advantage. It is exactly 1 for any rating that is the deviation gain of some distribution, so it cannot exceed 1
