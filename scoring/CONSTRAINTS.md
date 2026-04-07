# Scientist Constraints

This is a game-theoretic rating benchmark, not a predictive-model training task.

## Data

The scientist must use the provided local game definitions in [data/game_data.py](/home/user/data/game_data.py) for the scored benchmark:
- `augmented_biased_shapley_game()` for `biased_shapley_augmented`
- `rock_paper_scissors()` plus the cloned variant for `clone_invariance`
- `general_sum_reference_game()` plus a mixed-strategy augmentation for `mixture_invariance`
- `general_sum_reference_game()` plus arbitrary offsets for `offset_invariance`
- `dominance_test_game()` for `dominance_preserving`

No external datasets, modified payoff tables, or replacement benchmark games may be introduced for these scored experiments.

## Evaluation Protocol

The scientist must evaluate on the same scored experiments:
- `biased_shapley_augmented`
- `clone_invariance`
- `mixture_invariance`
- `offset_invariance`
- `dominance_preserving`

The standard evaluation entrypoint must remain:
- `bash scripts/evaluate.sh`

## Method Boundary

The scientist may improve or replace the current implementation, but the work must remain a principled strategy-rating method for normal-form games rather than a direct fit to the benchmark outputs.

The scientist may NOT:
- Hardcode the benchmark's target numbers
- Ignore the game structure and score the experiments with table-specific rules
- Change the scored game definitions while still claiming direct improvement on the same benchmark
- Change the meaning of `dev_gap`, `CCE_gap`, `max_diff`, `mixture_error`, or `dominance_violations`
- Skip any scored experiment

## Compliance Checklist
- [ ] Method operates on the provided normal-form games rather than hardcoded target outputs
- [ ] Evaluation uses the provided scored games
- [ ] All five scored experiments are evaluated
- [ ] Clone, mixture, offset, and dominance properties are preserved under the reported scores
