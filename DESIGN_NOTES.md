# Design Notes: Train/Test Evaluation for Deviation Ratings

## Split style: a visible seed vs. a hidden seed, generated at test time

The paper's claims are exact properties (equality on cyclic games, clone/mixture/offset invariance, dominance preservation, the strictest equilibrium) plus one empirical claim (Section 5.3: ratings drive population improvement in Sheriff). Train and test use the same metrics on different games:

- **Train / standard evaluation** (`eval/train/evaluate.py`, `eval/evaluate.py`, code in `eval/protocol.py`):
  - the five documented public games (paper Table 2, cloned RPS, the general-sum reference game with a fixed mixture and fixed offsets, the 2x2 dominance game);
  - the same generated families as the test, from the visible `TRAIN_SEED`;
  - a population run on that seed.
- **Hidden test** (`eval/test/evaluate.py`, self-contained, standard library only): about 210 property games and a population run, from a seed that exists only in that file. Clone positions, mixture weights, offsets, relabelings, dominance pairs, Sheriff policies and tie-breaking are all fixed by the evaluator.

The two files share no code; the hidden file carries its own copy of the machinery.

## Why a rating program, called once per population iteration

The test must rate games the method has never seen, so the method has to run at test time.

The population experiment is sequential: each iteration's meta-game depends on the previous ratings. So the program is called once per iteration. The property games ride along, spread over the calls, with the two games of every invariance pair in different calls. A program therefore cannot tell population games from property games: Sheriff meta-games appear among the property games too. Nor can it make an invariance pair consistent by transporting one game's answer to the other.

## Isolation

The evaluators run under `python3 -I`, and `scripts/evaluate_test.sh` ends in `exec`, so nothing a submission adds to `PYTHONPATH`, `sitecustomize.py` or the test script runs.

Inside the job container (a private PID namespace, recognised by PID 1 belonging to this user):
- **Process sweep.** The hidden test first stops every other process of the job except its ancestors and readers of their output pipes. A score-file watcher started before the test therefore cannot rewrite the result.
- **Per-call cleanup.** Every call runs in a fresh temporary directory and is the evaluator's subreaper. Its processes are killed before the output is read.
- **Stateless calls.** A call that changes files anywhere outside that directory fails, with system-managed paths excepted: version control and its credential shims, job logs, agent transcripts, the shared mount, and the container image.

## Why ratings must be the deviation gains of a returned CCE, and why strictness is scored

Constant ratings satisfy every invariance trivially. The paper defines a deviation rating as the deviation gain under an equilibrium. The method therefore returns the distribution, and the evaluator recomputes the gains and checks that they match the reported ratings and that the distribution is a CCE.

That alone left equilibrium selection unmeasured. A CCE with all gains at 0, or the least strict CCE, is also invariant, and two redteam shortcuts tied the reference that way. The paper selects the strictest equilibrium. The evaluator therefore computes, for every property game, the smallest largest deviation gain any CCE attains, a matrix-game value certified by a dual bound, and scores the excess as `strictness_gap`.

The full lexicographic order is not recomputed directly. That would require solving the same chain of degenerate LPs as the method, and those are numerically ill-posed in floating point on games with exactly dependent rows: we observed a 1e-16 violation moving an LP optimum by 4.7. A float ground truth for every level could penalise a correct method.

Levels below the top are certified through product games instead (iteration 13). If a game is the product of independent sub-games (players whose payoffs, up to offsets, depend only on their own block's actions), every block's deviation gains depend only on the distribution's marginal on that block, and the marginals can be chosen independently. The lexicographically strictest gain vector is then the merge of each block's own strictest vector, so within every block the largest gain equals that block's own min-max value. Each of those values is a single well-posed LP, certified by its dual bound like the top level. The blocks whose value is below the game's top sit deeper in the lexicographic order: in a game with bystanders whose gain levels lie between 0 and the original game's value, the original players' value is only reached after one selection step per level. This closed the three-LP shortcut that tied the reference in iteration 12's audit.

## Why bystander players

On random games the first min-max LP often has a unique solution, so a single LP already gives the deviation ratings. A bystander, a player whose payoff depends only on its own action, pins that LP at 0 without changing anyone's deviation ratings. The strictest equilibrium of the other players is then found only by the sequential freezing of Algorithm 1. With bystanders in every family, a single LP, an arbitrary CCE, and the earlier implementation's freeze-every-tight-constraint rule all fail. Bystanders had 1-3 actions until iteration 12; a selection capped at three LPs then still reached the original players' values on every test game, and the invariance checks could not see the difference because base and variant shared the same bystander. Bystanders now have 3-10 actions with levels placed between 0 and the base game's strictest value, some games have two of them, and `strictness_gap` checks every block.

## Why the population experiment (headroom)

On the property experiments the reproduced method sits at the bound of every metric, so they can only measure reproduction. Section 5.3 is where the paper's method is measured empirically and is not perfect. With 8 runs x 96 iterations its late gap ratio is about 0.58, against 0.67 for uniform averaging and 0.97 for random selection on the hidden test. The bound is 0, so a better method can score higher.

The horizon of 96 iterations (the paper runs 512) was chosen from 6 non-hidden seeds x 256 iterations (`redteam/population_diagnostics.json`). The reference beats uniform on every seed from 96 iterations on, and each test then takes about 3.5 minutes.
