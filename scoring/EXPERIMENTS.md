# Experiment Overview

Every experiment runs the rating program `scripts/rate.sh` on games supplied by the evaluator. The program is called once per population iteration (96 calls). Each call carries the iteration's population meta-games and a share of the property games; the two games of an invariance pair are always in different calls, and calls must be stateless.

The visible evaluators use the five documented public games plus families generated from a visible seed. The hidden test generates about 250 property games when it runs:
- 2- to 5-player games, some with one or two bystander players whose payoff depends only on their own action, and some that are products of two independent 2-player games;
- meta-games of random Sheriff populations;
- 3-player games above 1,000 and above 2,000 joint actions, and a cyclic population with 48 strategies per player (2,304 joint actions).

Each property metric is the maximum over the experiment's games (dominance violations are summed). Outputs must pass the validity gates in [TARGETS.md](/home/user/scoring/TARGETS.md), or the experiment is scored as failed.

Every property experiment also reports `strictness_gap`. For each game, the evaluator computes and certifies the smallest largest deviation gain that any CCE attains. In product games (bystanders, pairs of independent games) it does so for every independent block of players separately. `strictness_gap` is the largest amount by which the submitted equilibrium's largest deviation gain, within the game or within a block, exceeds that minimum. 0 means it is as strict as possible at the top level and on every block, and the blocks below the top probe the selection deeper in the lexicographic order.

## biased_shapley_augmented

Tests whether a method rates cyclic games without forcing an artificial linear order.
- Public game: paper Table 2 (biased Shapley game plus its Nash mixture N).
- Hidden games: relabeled, scaled, offset, cloned and populated variants (populations with up to 48 strategies per player), versions with one or two bystander players, zero-sum RPS, weighted RPS and RPS-lizard-Spock. In all of them the deviation ratings are provably equal.

Scored outputs:
- `dev_gap`: spread of the first cyclic player's ratings
- `CCE_gap`: recomputed total CCE regret of the submitted distribution
- `all_player_dev_gap`: spread across both cyclic players' actions
- `player_symmetry_gap`: mismatch between the two players' ratings of the same strategy
- `strictness_gap`

## clone_invariance

Tests whether duplicating a strategy leaves the original ratings unchanged.
- Public game: rock-paper-scissors with player 1's rock cloned.
- Hidden games: random games and Sheriff meta-games, each with one action cloned at a random position and all actions relabeled.

Scored outputs:
- `max_diff`: change in the ratings of the other players' strategies, the ones that face the clone
- `all_players_max_diff`: change over all original actions of all players
- `clone_source_gap`: absolute difference between the clone's rating and its source action's
- `strictness_gap`

## mixture_invariance

Tests whether adding a mixed strategy (weights fixed by the evaluator) leaves the original ratings unchanged and gives the new strategy the corresponding mixed rating. Public game: the general-sum reference game with a `[0.3, 0.7]` mixture for player 0.

Scored outputs:
- `original_max_diff`: largest change in any original rating (all players)
- `mixture_error`: absolute error between the mixed strategy's rating and the mixture of the original ratings
- `max_CCE_gap`: worst recomputed CCE regret of the base and augmented games
- `strictness_gap`

## offset_invariance

Tests whether adding offsets that depend only on the opponents' actions leaves ratings unchanged. Public game: offsets `[[10, -4], [7, -3]]` on the general-sum reference game.

Scored outputs:
- `max_diff`: largest absolute (uncentered) change of any rating
- `max_CCE_gap`: worst recomputed CCE regret of the base and offset-transformed games
- `strictness_gap`

## dominance_preserving

Tests whether a strictly dominant strategy is rated above the strategy it dominates. The evaluator computes the dominance pairs from each game. Every game has at least one pair with a constant payoff gap.

Scored outputs:
- `dominance_violations`: number of dominance pairs whose rating advantage is not positive
- `CCE_gap`: recomputed total CCE regret of the submitted distribution
- `min_margin`: smallest ratio of rating advantage to guaranteed payoff advantage. It is exactly 1 for any rating that is the deviation gain of some distribution, so it cannot exceed 1
- `strictness_gap`

## population_improvement

Tests whether a rating, used as the fitness measure of a simple evolutionary search, drives a population toward equilibrium in a general-sum game (paper Section 5.3, Sheriff).

Each of 8 runs keeps 8 random stochastic policies per player. Every iteration:
- the evaluator rates the 8x8 meta-game with the rating program;
- it drops each player's 2 lowest-rated policies;
- it adds the next 2 policies of a fixed random stream.

There are 96 iterations. Progress is the full-game CCE gap of the population under the meta-game's maximum-entropy CCE, measured every 8 iterations. Everything except the ratings is fixed by the evaluator.

Scored outputs:
- `late_gap_ratio` (primary): mean gap over the second half of the run divided by the initial gap
- `mean_gap_ratio`: mean gap over all checkpoints divided by the initial gap

Baselines: `uniform_payoff` (drop the lowest mean payoffs) and `random_selection`.
