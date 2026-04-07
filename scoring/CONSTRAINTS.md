# Scientist Constraints

This is a game-theoretic rating method, not a predictive model training task.

## Data

The scientist must use the provided local game definitions in [data/game_data.py](/home/user/data/game_data.py) for the scored benchmark:
- `augmented_biased_shapley_game()` for `biased_shapley_augmented`
- `rock_paper_scissors()` plus the cloned variant from the same file for `clone_invariance`

No external datasets, additional game families, or modified payoff tables may be introduced for these scored experiments.

## Evaluation Protocol

The scientist must evaluate on the same scored experiments:
- `biased_shapley_augmented`
- `clone_invariance`

The standard evaluation entrypoint must remain:
- `bash scripts/evaluate.sh`

## Method Boundary

The scientist may improve or replace the current implementation, but the work must remain a strategy-rating method for normal-form games rather than a generic statistical curve fit over the benchmark outputs.

The scientist may NOT:
- Hardcode the benchmark's target numbers
- Ignore the multi-strategy game structure and score the experiments with ad hoc table-specific rules
- Change the scored game definitions while still claiming direct improvement on the same benchmark
- Change the meaning of `dev_gap`, `CCE_gap`, or `max_diff`
- Skip either scored experiment

## Compliance Checklist
- [ ] Method operates on the provided normal-form games rather than hardcoded target outputs
- [ ] The method preserves the clone-invariance target measured by the benchmark
- [ ] Evaluation uses the provided local games
- [ ] Both scored experiments are evaluated
