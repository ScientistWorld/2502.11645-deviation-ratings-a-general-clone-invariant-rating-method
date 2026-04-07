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

Constraint metric in the same experiment:
- `CCE_gap`
- Direction: lower is better
- Interpretation: `CCE_gap = 0` means the selected recommendation distribution satisfies the equilibrium-feasibility check

## Constraint Targets

### `clone_invariance`

What it tests:
- Whether duplicating an existing strategy leaves the original strategies' ratings unchanged.

Primary metric:
- `max_diff`
- Direction: lower is better
- Interpretation: `max_diff = 0` means exact invariance of the original ratings under cloning

### `mixture_invariance`

What it tests:
- Whether adding a mixed strategy leaves all original ratings unchanged and gives the new strategy the corresponding mixed rating.

Primary metrics:
- `original_max_diff`
- `mixture_error`
- Direction: lower is better
- Interpretation: both metrics should be `0`

### `offset_invariance`

What it tests:
- Whether adding arbitrary offsets `b_p(a_-p)` leaves the deviation ratings unchanged.

Primary metric:
- `max_diff`
- Direction: lower is better
- Interpretation: `max_diff = 0` means exact offset invariance on the scored game

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

## Ablation Targets

No separate ablation experiment is currently packaged in `scoring/scores.json`.

Why:
- The current benchmark only contains exact property checks on explicit games and does not yet include a scored "remove the key idea" comparison.
- Future extensions should add any ablation here only when the ablation is also represented as its own experiment in both `scoring/reference.json` and `scoring/scores.json`.

The current benchmark only contains the five scored experiments listed above, which correspond one-to-one with `scoring/scores.json`.
