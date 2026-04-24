# Evaluation Targets

Run all scored evaluations with:
- `bash scripts/evaluate.sh`
- Or end-to-end: `bash scripts/reproduce.sh`

## Primary Target

### `biased_shapley_augmented`

What it tests:
- Whether the method avoids inventing a strict order on the augmented biased Shapley game and instead treats `R`, `P`, `S`, and `N` as one top group.

Primary metric:
- `dev_gap`
- Direction: lower is better
- Interpretation: `dev_gap = 0` means the four deviation ratings are equal

Additional scored checks in the same experiment:
- `CCE_gap`
- Direction: lower is better
- Interpretation: `CCE_gap = 0` means the selected recommendation distribution satisfies the equilibrium-feasibility check
- `all_player_dev_gap`
- Direction: lower is better
- Interpretation: `all_player_dev_gap = 0` means the equality result holds across both players' action sets, not only one visible slice
- `player_symmetry_gap`
- Direction: lower is better
- Interpretation: `player_symmetry_gap = 0` means corresponding actions receive the same rating for both players in the symmetric benchmark

## Constraint Targets

### `clone_invariance`

What it tests:
- Whether duplicating an existing strategy leaves the original strategies' ratings unchanged.

Primary metric:
- `max_diff`
- Direction: lower is better
- Interpretation: `max_diff = 0` means exact invariance of the original ratings under cloning

Additional scored checks:
- `all_players_max_diff`
- Direction: lower is better
- Interpretation: `all_players_max_diff = 0` means the invariance check holds across both players
- `clone_source_gap`
- Direction: lower is better
- Interpretation: `clone_source_gap = 0` means the added clone receives the same rating as its source action

### `mixture_invariance`

What it tests:
- Whether adding a mixed strategy leaves all original ratings unchanged and gives the new strategy the corresponding mixed rating.

Primary metrics:
- `original_max_diff`
- `mixture_error`
- Direction: lower is better
- Interpretation: both metrics should be `0`

Additional scored check:
- `max_CCE_gap`
- Direction: lower is better
- Interpretation: `max_CCE_gap = 0` means the recommendation distributions remain equilibrium-feasible in both the base and augmented games

### `offset_invariance`

What it tests:
- Whether adding arbitrary offsets `b_p(a_-p)` leaves the deviation ratings unchanged.

Primary metric:
- `max_diff`
- Direction: lower is better
- Interpretation: `max_diff = 0` means exact offset invariance on the scored game

Additional scored check:
- `max_CCE_gap`
- Direction: lower is better
- Interpretation: `max_CCE_gap = 0` means the recommendation distributions remain equilibrium-feasible before and after the offset transformation

## Secondary Property Target

### `dominance_preserving`

What it tests:
- Whether a dominant strategy is never rated below a dominated one.

Primary metric:
- `dominance_violations`
- Direction: lower is better
- Interpretation: `0` means every encoded dominance relation is respected

Constraint metric in the same experiment:
- `CCE_gap`
- Direction: lower is better
- Interpretation: the equilibrium-feasibility check should still be satisfied

Additional scored check:
- `min_margin`
- Direction: higher is better
- Interpretation: larger positive margins mean the dominant action is separated more clearly from the dominated action

## Ablation Targets

No separate ablation experiment is currently packaged in `scoring/scores.json`.

Why:
- The current benchmark only contains exact property checks on explicit games and does not yet include a scored "remove the key idea" comparison.
- Future extensions should add any ablation here only when the ablation is also represented as its own experiment in both `scoring/reference.json` and `scoring/scores.json`.

The current benchmark only contains the five scored experiments listed above, which correspond one-to-one with `scoring/scores.json`.
