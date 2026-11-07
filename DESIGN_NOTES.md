# Design Notes: Train/Test Evaluation for Deviation Ratings

## Split style: public games vs. hidden games generated at test time

The paper's claims are exact properties (equality on cyclic games, clone/mixture/offset invariance, dominance preservation), so train and test use the same metrics on different games:

- **Train / standard evaluation** (`eval/train/evaluate.py`, `eval/evaluate.py`, shared code in `eval/protocol.py`): the five documented public games (paper Table 2, cloned RPS, the general-sum reference game with a fixed mixture and fixed offsets, the 2x2 dominance game).
- **Hidden test** (`eval/test/evaluate.py`, self-contained, standard library only): about 190 games generated at test time from a seed that exists only in that file. They come from the same five families, built on random 2- and 3-player general-sum, zero-sum and common-interest games, cyclic games with provably equal ratings, and games with a bystander player. Clone positions, mixture weights, offsets, relabelings and dominance pairs are all fixed by the evaluator.

An earlier version scored artifacts the method precomputed on the five public games, splitting metrics between train and test ("metric triangulation"). Constant ratings plus one special-cased dominance answer saturated that test, and margins could be inflated without bound. `HARDENING.md` documents the replacement.

## Why a rating program instead of artifacts

The test must rate games the method has never seen, so the method has to run at test time. The evaluator writes anonymised, shuffled games and runs `scripts/rate.sh` in a fresh temporary directory. It acts as the reaper of every process the program starts, so detached daemons are killed, and only then reads and scores the output. The evaluators run under `python3 -I` and `scripts/evaluate_test.sh` ends in `exec`, so nothing a submission adds to `PYTHONPATH`, `sitecustomize.py` or the test script runs.

## Why ratings must be the deviation gains of a returned CCE

Constant ratings satisfy every invariance trivially. The paper defines a deviation rating as the deviation gain under an equilibrium, which couples the ratings to the game: the method returns the distribution, and the evaluator recomputes the gains and checks that they match the reported ratings and that the distribution is a CCE. This removes constant answers, rescaling (margins can no longer grow without bound) and any number the method reports about itself. Within this family the open question is equilibrium selection, which is what the paper contributes.

## Why bystander players

On random games the first min-max LP usually has a unique solution, so a single LP already gives the deviation ratings. A bystander, a player whose payoff depends only on its own action, pins that LP at 0 without changing anyone's deviation ratings. The strictest equilibrium of the other players is then found only by the sequential freezing of Algorithm 1. With bystanders in every family, a single LP, an arbitrary CCE, and the earlier implementation's freeze-every-tight-constraint rule all fail on every sampled suite, while the reference passes all of them (`redteam/diagnostics.json`).
