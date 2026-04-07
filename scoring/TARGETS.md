# Evaluation Targets

Run all scored evaluations with:
- `bash scripts/evaluate.sh`
- Or end-to-end: `bash scripts/reproduce.sh`

## Primary Target

### `biased_shapley_augmented`

What it tests:
- Whether the method avoids inventing a strict order on the augmented biased Shapley game and instead treats the four strategies as one top group.

Primary metric:
- `dev_gap`
- Direction: lower is better
- Interpretation: `dev_gap = 0` means all four player-0 strategy ratings are equal

Secondary metric recorded in the same experiment:
- `CCE_gap`
- Direction: lower is better
- Interpretation: `CCE_gap = 0` means the selected recommendation distribution satisfies the equilibrium-feasibility check exactly

How to run:
- `bash scripts/evaluate.sh`

## Constraint Target

### `clone_invariance`

What it tests:
- Whether duplicating an existing strategy leaves the original strategies' ratings unchanged.

Primary metric:
- `max_diff`
- Direction: lower is better
- Interpretation: `max_diff = 0` means exact invariance of the original ratings under cloning

How to run:
- `bash scripts/evaluate.sh`

## Ablation Target

No separate scored ablation experiment is packaged at the current `core_claim` milestone.

The current benchmark only contains the two scored experiments listed above, which correspond one-to-one with `scoring/scores.json`.
