# Scientist Constraints

This is a game-theoretic rating benchmark, not a predictive-model training task.

## Method Interface

The method is the rating program `scripts/rate.sh GAMES_JSON RATINGS_JSON`. The contract is in [briefing/evaluation.md](/home/user/briefing/evaluation.md). For every game it must return:
- one finite real rating per action of every player, and
- the joint distribution those ratings come from: a probability vector over joint actions, C order.

The distribution must be a coarse correlated equilibrium, and each rating must equal that distribution's deviation gain for the action. Outputs that break this contract are scored as failed rather than ranked.

## Data

The evaluators supply the scored games; the method does not choose or edit them:
- `bash scripts/evaluate.sh` and `bash scripts/evaluate_train.sh` use the five documented public games. `data/game_data.py` contains the same definitions for development use.
- `bash scripts/evaluate_test.sh` generates its own hidden games at test time. It reads nothing from `data/`, `checkpoints/`, `baseline/` or `scoring/reference.json`.

No external datasets are needed or used.

## Evaluation Protocol

The scientist must keep the five scored experiments and their entrypoints:
- `biased_shapley_augmented`, `clone_invariance`, `mixture_invariance`, `offset_invariance`, `dominance_preserving`
- `bash scripts/evaluate.sh` (standard), `bash scripts/evaluate_train.sh`, `bash scripts/evaluate_test.sh` (hidden, no arguments)

`eval/` and `scripts/evaluate*.sh` belong to the benchmark. Baselines, transformations, mixture weights, offsets, dominance pairs, tolerances and the test size are all fixed there.

## Method Boundary

The scientist may improve or replace the implementation behind `scripts/rate.sh`, but the result must remain a principled strategy-rating method for normal-form games, not a fit to the benchmark outputs.

The scientist may NOT:
- Hardcode the benchmark's target numbers or special-case recognizable games
- Ignore the game structure and score the experiments with table-specific rules
- Change the scored game definitions, evaluators, tolerances or baselines while still claiming improvement on this benchmark
- Change the meaning of `dev_gap`, `CCE_gap`, `max_diff`, `mixture_error`, `dominance_violations` or `min_margin`
- Skip any scored experiment, or read or modify the hidden evaluator from the rating program

## Compliance Checklist
- [ ] `scripts/rate.sh` rates any finite 2- or 3-player normal-form game it is given (including players with a single action)
- [ ] Ratings are the deviation gains of the returned CCE
- [ ] All five scored experiments are evaluated through the provided entrypoints
- [ ] Clone, mixture, offset and dominance properties hold on the hidden games, not only the public ones
