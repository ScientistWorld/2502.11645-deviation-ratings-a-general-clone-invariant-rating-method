# Scientist Constraints

This is a game-theoretic rating benchmark, not a predictive-model training task.

## Method Interface

The method is the rating program `scripts/rate.sh GAMES_JSON RATINGS_JSON`. The contract is in [briefing/evaluation.md](/home/user/briefing/evaluation.md). For every game it must return:
- one finite real rating per action of every player, and
- the joint distribution those ratings come from: a probability vector over joint actions, C order.

The distribution must be a coarse correlated equilibrium, and each rating must equal that distribution's deviation gain for the action. Outputs that break this contract are scored as failed rather than ranked.

The program is called about 96 times per evaluation, with a few games per call. Each call must:
- finish within 300 s, with at most 2400 s over all calls;
- leave no files behind or changed outside its temporary directory (`$TMPDIR`);
- leave no processes behind.

Calls are independent: the two games of an invariance pair arrive in different calls, and inside the job container any state carried from one call to another fails the call. The same program rates the population meta-games and the property games, and the program cannot tell which is which.

## Data

The evaluators supply the scored games; the method does not choose or edit them:
- `bash scripts/evaluate.sh` and `bash scripts/evaluate_train.sh` use the five documented public games plus families and a population run from a visible seed. `data/game_data.py` contains the public game definitions for development use.
- `bash scripts/evaluate_test.sh` generates its own hidden games at test time. It reads nothing from `data/`, `checkpoints/`, `baseline/` or `scoring/reference.json`. Before it starts it stops every other process of the submission.

No external datasets are needed or used.

## Evaluation Protocol

The scientist must keep the six scored experiments and their entrypoints:
- `biased_shapley_augmented`, `clone_invariance`, `mixture_invariance`, `offset_invariance`, `dominance_preserving`, `population_improvement`
- `bash scripts/evaluate.sh` (standard), `bash scripts/evaluate_train.sh`, `bash scripts/evaluate_test.sh` (hidden, no arguments)

`eval/` and `scripts/evaluate*.sh` belong to the benchmark. They fix:
- baselines, transformations, mixture weights, offsets and dominance pairs;
- the strictest achievable deviation gain;
- the Sheriff game, its candidate policies and the gap measure;
- tolerances, time limits and the test size.

## Method Boundary

The scientist may improve or replace the implementation behind `scripts/rate.sh`, but the result must remain a principled strategy-rating method for normal-form games, not a fit to the benchmark outputs.

The scientist may NOT:
- Hardcode the benchmark's target numbers or special-case recognizable games (including population meta-games)
- Ignore the game structure and score the experiments with table-specific rules
- Change the scored game definitions, evaluators, tolerances, time limits or baselines while still claiming improvement on this benchmark
- Change the meaning of `dev_gap`, `CCE_gap`, `max_diff`, `mixture_error`, `dominance_violations`, `min_margin`, `strictness_gap` or the gap ratios
- Skip any scored experiment, or read or modify the hidden evaluator from the rating program
- Keep state between calls, leave processes running, or touch score files

## Compliance Checklist
- [ ] `scripts/rate.sh` rates any finite 2- or 3-player normal-form game it is given (including players with a single action and games above 1,000 joint actions)
- [ ] Ratings are the deviation gains of the returned CCE
- [ ] Each call is stateless and finishes within 300 s
- [ ] All six scored experiments are evaluated through the provided entrypoints
- [ ] Clone, mixture, offset and dominance properties hold on the hidden games, not only the public ones
