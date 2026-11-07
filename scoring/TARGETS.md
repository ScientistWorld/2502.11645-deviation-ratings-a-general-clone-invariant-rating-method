# Evaluation Targets

A method is the rating program `bash scripts/rate.sh GAMES_JSON RATINGS_JSON`. For every game it returns ratings and the joint distribution they come from (contract: [briefing/evaluation.md](/home/user/briefing/evaluation.md)). Run the scored evaluations with:
- `bash scripts/evaluate.sh` (visible suite → `scoring/scores.json`)
- `bash scripts/evaluate_train.sh` (visible suite → `scoring/scores_train.json`)
- `bash scripts/evaluate_test.sh` (hidden games generated at test time → `scoring/scores_test.json`)
- end to end: `bash scripts/reproduce.sh`

## Constraint gates (all experiments)

These are pass/fail conditions, not traded-off metrics. A game fails if:
- any rating or probability is not a finite real number;
- the shape is wrong (exactly one rating per action of every player, one probability per joint action);
- the distribution is negative or does not sum to 1;
- the distribution is not a coarse correlated equilibrium;
- the ratings differ from the distribution's deviation gains by more than `1e-6 * payoff scale`;
- for a noisy observation (experiment `noisy_clone_resilience`) that returns its own estimate `payoffs`: the estimate has the wrong shape, is not finite, or moves an observed payoff by more than the noise bound (the two checks above then use the estimate);
- the call carrying it crashed, timed out (300 s per call, 2400 s in total), wrote malformed output, or created, changed or deleted files outside its temporary directory.

When a game fails, every experiment containing it is scored as failed: lower-is-better metrics are set to `1e6` and `min_margin` to `-1e6`. A failure on any population meta-game fails `population_improvement`. Metrics are recomputed from the payoffs and the submitted distribution, never taken from numbers the method reports.

## Primary Target

### `biased_shapley_augmented`

What it tests:
- Whether the method avoids inventing a strict order in cyclic games. The public game is the paper's Table 2 game with R, P, S and N. The hidden games are transformed and populated cyclic games whose deviation ratings are provably all equal.

Primary metric:
- `dev_gap` (lower is better): largest spread of the first cyclic player's ratings. `0` means the ratings are equal.

Additional scored checks:
- `all_player_dev_gap` (lower is better): spread across both cyclic players' actions.
- `player_symmetry_gap` (lower is better): largest same-strategy mismatch between the two players.
- `CCE_gap` (lower is better): recomputed total CCE regret of the submitted distribution. It is 0 for every output that passes the gates.
- `strictness_gap` (lower is better): how much the selected equilibrium's largest deviation gain exceeds the smallest largest deviation gain any CCE of the game attains. In games built from independent sub-games (bystander players, pairs of independent games) this is checked on every independent block of players, so a selection that is strict only at the top level fails on the blocks below it. On the biased Shapley games the minimum is -680/241 times the payoff scale, the common deviation rating of paper Table 2, also for the cyclic players of a game with bystanders.

## Headroom Target

### `population_improvement`

What it tests:
- Whether ratings, used to choose which Sheriff policies survive in a population search, drive the population toward equilibrium in the full game (paper Section 5.3). 8 runs x 96 iterations, all draws fixed by the evaluator.

Primary metric:
- `late_gap_ratio` (lower is better): mean full-game CCE gap over the second half of the run divided by the initial gap.

Additional scored check:
- `mean_gap_ratio` (lower is better): mean gap over all checkpoints divided by the initial gap.

The reproduced method is not at the bound of this metric. The paper reports that deviation ratings reduce the gap where uniform averaging stalls; a better rating can reduce it further. Changing the equilibrium selection to do so usually costs `strictness_gap` or invariance in the property experiments.

### `noisy_clone_resilience`

What it tests:
- Whether ratings computed from noisy evaluation data that contain near-copies of a strategy stay close to the deviation ratings of the true game. 96 hidden instances: random 2- and 3-player general-sum and zero-sum games and the paper's model vs model vs task game, each observed twice with every payoff within the noise bound 0.05 of the truth, once padded with 3-10 near-copies of one action (one task) and once without.

Primary metric:
- `rating_error` (lower is better): mean over the padded observations of the mean absolute difference between each action's rating and the true game's exact deviation rating of the action it observes, in units of the noise bound.

Additional scored check:
- `clean_rating_error` (lower is better): the same over the observations without near-copies, measured with independent noise.

Rating the observation as given is valid but not optimal: a method may rate its own estimate of the true game, within the noise bound. 0 is unattainable from noisy data, so a better method can always score higher. These games carry `noise_bound`, so nothing a method does differently on them changes its results on the exact games of the other experiments.

## Constraint Targets

### `clone_invariance`

What it tests:
- Whether duplicating a strategy leaves every original rating unchanged and gives the clone its source's rating.

Primary metric:
- `max_diff` (lower is better): largest clone-induced change in the ratings of the other players' strategies, the ones facing the clone.

Additional scored checks:
- `all_players_max_diff` (lower is better): largest change over all original actions of all players.
- `clone_source_gap` (lower is better): clone's rating versus its source's.
- `strictness_gap` (lower is better): as above.

### `mixture_invariance`

What it tests:
- Whether adding a mixed strategy, with weights fixed by the evaluator, leaves all original ratings unchanged and gives the new strategy the corresponding mixed rating.

Primary metrics:
- `original_max_diff` (lower is better): largest change in any original rating, all players.
- `mixture_error` (lower is better): mixture's rating minus the same mixture of the original ratings.

Additional scored checks:
- `max_CCE_gap` (lower is better): worst recomputed CCE regret of the base and augmented games.
- `strictness_gap` (lower is better).

### `offset_invariance`

What it tests:
- Whether adding arbitrary offsets `b_p(a_-p)`, fixed by the evaluator, leaves every rating unchanged.

Primary metric:
- `max_diff` (lower is better): largest absolute (uncentered) change of any rating.

Additional scored checks:
- `max_CCE_gap` (lower is better): worst recomputed CCE regret of the base and offset games.
- `strictness_gap` (lower is better).

## Secondary Property Target

### `dominance_preserving`

What it tests:
- Whether a strictly dominant strategy is rated above the strategy it dominates. The evaluator derives the dominance pairs from the game itself.

Primary metric:
- `dominance_violations` (lower is better): number of strictly dominated pairs whose rating advantage is not positive.

Additional scored checks:
- `CCE_gap` (lower is better): recomputed total CCE regret.
- `min_margin` (higher is better, at most 1): smallest ratio of rating advantage to guaranteed payoff advantage. Every game contains a constant-gap pair, on which any rating that is the deviation gain of a distribution scores exactly 1. A larger rating separation cannot raise it, and a reversed order lowers it.
- `strictness_gap` (lower is better).

## Baselines

`uniform_payoff` is scored in every experiment (in `noisy_clone_resilience` as the deviation gains of the uniform joint distribution, so it is on the deviation-rating scale). `zero_rating` and `negative_uniform_payoff` are scored in dominance, and `random_selection` in the population experiment. All are computed by the evaluator on the same games.

## Ablation Targets

No separate ablation experiment is scored. The hardening audit (`HARDENING.md`, `redteam/property_diagnostics.json`, `redteam/population_diagnostics.json`) records what happens with simpler equilibrium selections:
- the first LP of Algorithm 1 only;
- any feasible CCE;
- the least strict CCE;
- a CCE with all gains set to 0;
- the maximum-welfare CCE.

They are diagnostics, not scored experiments.

The benchmark contains exactly the seven scored experiments above, which correspond one-to-one with `scoring/scores.json`.
