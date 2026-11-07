# Evaluation Targets

A method is the rating program `bash scripts/rate.sh GAMES_JSON RATINGS_JSON`. For every game it returns ratings and the joint distribution they come from (contract: [briefing/evaluation.md](/home/user/briefing/evaluation.md)). Run the scored evaluations with:
- `bash scripts/evaluate.sh` (public games → `scoring/scores.json`)
- `bash scripts/evaluate_train.sh` (public games → `scoring/scores_train.json`)
- `bash scripts/evaluate_test.sh` (hidden games generated at test time → `scoring/scores_test.json`)
- end to end: `bash scripts/reproduce.sh`

## Constraint gates (all experiments)

These are pass/fail conditions, not traded-off metrics. A game fails if:
- any rating or probability is not a finite real number;
- the shape is wrong (exactly one rating per action of every player, one probability per joint action);
- the distribution is negative or does not sum to 1;
- the distribution is not a coarse correlated equilibrium;
- the ratings differ from the distribution's deviation gains by more than `1e-6 * payoff scale`.

When a game fails, every experiment containing it is scored as failed: lower-is-better metrics are set to `1e6` and `min_margin` to `-1e6`. Metrics are recomputed from the payoffs and the submitted distribution, never taken from numbers the method reports.

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

## Constraint Targets

### `clone_invariance`

What it tests:
- Whether duplicating a strategy leaves every original rating unchanged and gives the clone its source's rating.

Primary metric:
- `max_diff` (lower is better): largest clone-induced change in the ratings of the other players' strategies, the ones facing the clone.

Additional scored checks:
- `all_players_max_diff` (lower is better): largest change over all original actions of all players.
- `clone_source_gap` (lower is better): clone's rating versus its source's.

### `mixture_invariance`

What it tests:
- Whether adding a mixed strategy, with weights fixed by the evaluator, leaves all original ratings unchanged and gives the new strategy the corresponding mixed rating.

Primary metrics:
- `original_max_diff` (lower is better): largest change in any original rating, all players.
- `mixture_error` (lower is better): mixture's rating minus the same mixture of the original ratings.

Additional scored check:
- `max_CCE_gap` (lower is better): worst recomputed CCE regret of the base and augmented games.

### `offset_invariance`

What it tests:
- Whether adding arbitrary offsets `b_p(a_-p)`, fixed by the evaluator, leaves every rating unchanged.

Primary metric:
- `max_diff` (lower is better): largest absolute (uncentered) change of any rating.

Additional scored check:
- `max_CCE_gap` (lower is better): worst recomputed CCE regret of the base and offset games.

## Secondary Property Target

### `dominance_preserving`

What it tests:
- Whether a strictly dominant strategy is rated above the strategy it dominates. The evaluator derives the dominance pairs from the game itself.

Primary metric:
- `dominance_violations` (lower is better): number of strictly dominated pairs whose rating advantage is not positive.

Additional scored checks:
- `CCE_gap` (lower is better): recomputed total CCE regret.
- `min_margin` (higher is better, at most 1): smallest ratio of rating advantage to guaranteed payoff advantage. Every game contains a constant-gap pair, on which any rating that is the deviation gain of a distribution scores exactly 1. A larger rating separation cannot raise it, and a reversed order lowers it.

## Baselines

`uniform_payoff` is scored in every experiment. `zero_rating` and `negative_uniform_payoff` are scored in dominance. All three are computed by the evaluator on the same games.

## Ablation Targets

No separate ablation experiment is packaged in `scoring/scores.json`. The hardening audit (`HARDENING.md`, `redteam/diagnostics.json`) records what happens without the sequential freezing step: a single min-max LP, any CCE, or the earlier implementation's freeze-every-tight-constraint rule. All three fail the hidden invariance checks, but they are diagnostics, not scored experiments.

The benchmark contains exactly the five scored experiments above, which correspond one-to-one with `scoring/scores.json`.
