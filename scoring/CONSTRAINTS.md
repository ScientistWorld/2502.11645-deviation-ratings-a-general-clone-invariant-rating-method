# Scientist Constraints

This is a game-theoretic rating method, not a predictive model training task.

## Data

The scientist must use the provided local games for evaluation.
No external datasets or additional game families may be introduced for the scored experiments.

## Evaluation Protocol

The scientist must evaluate on the same scored experiments:
- `biased_shapley_augmented`
- `clone_invariance`

## Method Boundary

The scientist may improve or replace the current implementation, but the work must remain a strategy-rating method for normal-form games rather than a generic statistical curve fit over the benchmark outputs.

The scientist may NOT:
- Hardcode the benchmark's target numbers
- Ignore the multi-strategy game structure and score the experiments with ad hoc table-specific rules
- Change the scored game definitions while still claiming direct improvement on the same benchmark
- Skip either scored experiment

## Compliance Checklist
- [ ] Method operates on the provided normal-form games rather than hardcoded target outputs
- [ ] The method preserves the clone-invariance target measured by the benchmark
- [ ] Evaluation uses the provided local games
- [ ] Both scored experiments are evaluated
