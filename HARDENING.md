# Hardening report (iteration 11)

`REDTEAM.md` replayed 45 shortcuts through the hidden test:
- **Beat the reference (5):** margin inflation ×2 (rating_inflation, unbounded_margin), a phantom dominance action, a startup hook that rewrote the score file, and decoy checkpoints that took precedence over the real method.
- **Tied it:** about 20 more, including a "public answers" template that never computes a rating.

The root cause was structural. The hidden test scored numbers the method had precomputed on five public games, and it trusted the method's action lists, dominance pairs, mixture weights and probability vectors.

This iteration replaces the scoring contract, re-runs the reference from the final code, and replays all 45 shortcuts plus 6 new probes aimed at the new contract. After hardening:
- **None** of the 51 beats the reference.
- Every shortcut that does not run the paper's method scores below it.
- The 6 that tie run the honest method underneath, and their manipulation is either ignored or harmless.

## What changed

| ID | Fix | Where |
|---|---|---|
| F1 | **Rating-program contract and hidden games generated at test time.** The method is `scripts/rate.sh GAMES RATINGS`, run by every evaluator. The hidden test builds 186 games from a seed that exists only in `eval/test/evaluate.py`, gives them opaque ids, shuffles them, and runs the program once in a fresh temporary directory. Families: 15 cyclic games with provably equal ratings, 26 clone pairs, 26 mixture pairs, 26 offset pairs, 15 dominance games. They are built on 2- and 3-player general-sum, zero-sum and common-interest games, with random insertion positions and relabelings. | `eval/test/evaluate.py`, `scripts/rate.sh`, `method/rate.py` |
| F2 | **Validity gates.** Every value must be a finite JSON number: NaN/Infinity constants, overflowing literals, strings, booleans and nulls are rejected at parse time. Shapes come from the game. The distribution must be non-negative and sum to 1 ± 1e-6, with no silent renormalization. It must be a CCE (largest deviation gain ≤ 1e-6·scale), and the ratings must equal its deviation gains (± 1e-6·scale). A failed game fails every experiment it belongs to, scored 1e6 on lower-is-better metrics and −1e6 on `min_margin`. A crash, timeout or malformed output fails all five. | `validate_result`, `run_rater` |
| F3 | **Everything recomputed.** Metrics use deviation gains recomputed from the payoffs and the submitted distribution. Reported ratings are only checked against them. Extra fields (`cce_gap`, `success`, `min_margin`, `dominance_pairs`, `mixture`, `action_names`, ...) are ignored. | `score_suite` |
| F4 | **The evaluator fixes the comparisons.** It fixes action sets, both players' presence, clone sources and positions, mixture weights, offsets, relabelings, and dominance pairs (all strictly dominated pairs, computed from each game), plus tolerances, test size, the proposed-method id and all baselines (`uniform_payoff` in every experiment; `zero_rating` and `negative_uniform_payoff` in dominance). The hidden test reads nothing from `data/`, `baseline/`, `checkpoints/` or `scoring/reference.json`. | `eval/test/evaluate.py` |
| F5 | **Every advertised constraint on the hidden path.** It now checks original-rating drift under mixtures, absolute (uncentered) offset differences, and a valid CCE for both games of every clone pair. `min_margin` is the rating advantage divided by the guaranteed payoff advantage. Every game has a constant-gap pair, on which this is exactly 1 for any deviation-gain rating, so it is bounded and cannot be inflated. | metric functions |
| F6 | **Isolation.** The evaluators run as `exec python3 -I ...`: no `PYTHONPATH`, user site or working directory, and nothing appended to the shell script runs. `eval/test` is standard-library only. The evaluator makes itself the subreaper of the rating program and kills its process group and every remaining descendant, including double-forked daemons, before it reads or scores anything. The output must be a regular file under 64 MB. The score file is deleted at start and written fresh at the end. | `run_rater`, `scripts/evaluate*.sh` |
| F7 | **One declared method location.** Only `scripts/rate.sh` is scored as `deviation_rating`. Checkpoint directories are never read, so alternate checkpoints cannot shadow the method and method ids cannot collide with baselines. | all evaluators |
| F8 | **Bystander players.** These are players whose payoff depends only on their own action. They appear in every family (in about a quarter of the random games and in 3 of the 15 cyclic games). Such a player leaves everyone's deviation ratings unchanged but pins the first LP of Algorithm 1 at ε = 0. Without bystanders, a single min-max LP tied the reference on the official suite (job 1). With them it fails on every sampled suite. | `_with_bystander` |
| F9 | **Reference fix: the paper's freezing rule.** `method/deviation_rating.py` had also frozen every constraint that happened to be tight at the returned vertex. On degenerate optima that freezes ratings later iterations should lower, so the ratings depend on the solver. The default is now the paper's rule (Section 4.1: freeze constraints with nonzero duals). Evidence is below. | `method/deviation_rating.py` |
| F10 | **Visible side mirrors the test.** `scripts/evaluate.sh` and `scripts/evaluate_train.sh` run the same protocol on the five public games (`eval/protocol.py`), report the full metric set and the uniform baseline in every experiment, and enforce the same gates. | `eval/protocol.py`, `eval/train/evaluate.py`, `eval/evaluate.py` |

Hidden test source SHA-256 in every replay: `3b55cfa0783573907ca959e17ace70c75e9ea0e462ca279585b4a7d439685eb7`. The pre-hardening hidden test was `2764b05c…3c61`.

## Reference score, before and after

Before is the pre-hardening hidden test (`redteam/reference_seeds/seed_0/scores_test.json`). After is the hardened hidden test, rerun from the final code (`scoring/scores_test.json`, identical in 3 independent runs, `redteam/reference_runs/`).

| Experiment | Reference before | Reference after | Uniform baseline after |
|---|---|---|---|
| biased_shapley_augmented | all_player_dev_gap 0, player_symmetry_gap 0, CCE_gap 0 (no `dev_gap`) | dev_gap 0, all_player_dev_gap 0, player_symmetry_gap 0, CCE_gap 0 | 2.2555 / 3.4 / 2.029333 / 3.209813 |
| clone_invariance | all_players_max_diff 0, clone_source_gap 0 (no `max_diff`) | max_diff 0, all_players_max_diff 0, clone_source_gap 0 | 0.270667 / 0.270667 / 0 |
| mixture_invariance | mixture_error 0, max_CCE_gap 0 (no drift check) | original_max_diff 0, mixture_error 0, max_CCE_gap 0 | 0.13951 / 0 / 1.355 |
| offset_invariance | max_diff 0 (centered), max_CCE_gap 0; uniform baseline also **0** | max_diff 0 (absolute), max_CCE_gap 0 | 4.616 / 1.522375 |
| dominance_preserving | violations 0, min_margin 1, CCE_gap 0 (zero baseline 2/0/1, negative uniform 2/−1/1) | violations 0, min_margin 1, CCE_gap 0 | uniform 0 / 1 / 1.580406; zero 67 / 0 / 1.580406; negative uniform 67 / −82.875 / 1.580406 |

The reference keeps its exact scores. The baselines now show the paper's claim in the paper's direction on every experiment: uniform averaging is not equal on cycles, not clone, mixture or offset invariant, and not an equilibrium. Before hardening, the hidden offset check gave the uniform baseline the same 0 as the reference.

The visible side changed too, and was regenerated from the reference run (`scoring/scores_train.json`, `scoring/scores.json`, public games):
- **Reference:** every gap 0, violations 0, `min_margin` 1.
- **Uniform baseline:**
  - Shapley: 1.25 / 1.25 / 0 / 0.941909
  - clone: 0.25 / 0.25 / 0
  - mixture: 0.133333 / 0 / 0.5
  - offset: 3.0 / 0.5
  - dominance: 0 / 1 / 1
- **Zero and negative-uniform baselines:** 2 / 0 / 1 and 2 / −1 / 1.

The paper's reported results and the experiment weights in `scoring/reference.json` are unchanged. I added `uniform_payoff` baseline rows to Shapley, clone, mixture and dominance, and the metric descriptions now match the definitions above. `max_diff` in clone invariance now measures the strategies that face the clone: the visible public clone is player 1's rock, and `max_diff` is player 0's ratings.

**Larger than seed noise.** The method is deterministic, and the 3 reference runs are byte-identical. Run through the hidden protocol with 10 more seeds, the reference scores exactly 0 on every invariance metric in **11/11** suites, at default and at tight LP tolerances. Every cheap alternative fails every suite. Its largest error per suite runs from 3.7 to 7.9 for a single LP, any CCE, or the first pure Nash equilibrium, and the uniform-distribution gains are failed by the CCE gate (`redteam/diagnostics.json`).

**Why the reference implementation changed (F9).** Same 11 suites, everything else identical:

| Program | Perfect suites | Example on the official suite |
|---|---|---|
| reference, paper's nonzero-dual rule (shipped) | 11/11 | all 0 |
| reference, nonzero-dual rule, LP tolerances 1e-10 | 11/11 | all 0 |
| previous rule (also freezes every tight constraint) | 0/11 | Shapley dev_gap 5.987, clone all-players 0.827, mixture drift 1.491 |
| previous rule, tight tolerances | 0/11 | clone 1.435, mixture 1.491 |

The training method is not changed. The fix restores the rule the paper states, and the paper's Table 2 result (all four ratings −2720/964) is reproduced with it.

## Every shortcut, before and after

"Before" is the REDTEAM hidden-test result. "After" is the hardened hidden test (`redteam/<name>/scores_test.json`; the mechanical comparison is in `redteam/shortcut_comparisons.json`). "Failed (5/5)" means every proposed-method metric in all five experiments is the failure score (1e6, `min_margin` −1e6). Shortcut-specific workspace edits were reapplied as in REDTEAM. Where the shortcut is a manipulation rather than a replacement method, it is applied on top of the honest method's output, so a tie means "no gain" rather than "missed".

| # | Shortcut | Before | Fix | After |
|---|---|---|---|---|
| 1 | public_answers | R exactly (constant ratings, one feasibility LP, special-cased dominance game) | F1, F2: ratings must be the deviation gains of the returned CCE; hidden games | Failed (5/5) |
| 2 | uniform_payoffs | U (worse) | F2 CCE gate | Failed (5/5) |
| 3 | constant_zero | R except dominance (2 violations, margin 0) | F2 consistency gate | Failed (5/5) |
| 4 | copy_input | worse (Shapley spread 10) | F2 | Failed (5/5) |
| 5 | empty_artifacts | crash, no score | F2: missing output is a failed game | Failed (5/5) |
| 6 | direct_scores | U; prewritten files overwritten | F6 score file deleted at start; F2 | Failed (5/5) |
| 7 | reported_fields | U | F3 reported fields ignored; F2 | Failed (5/5) |
| 8 | null_ratings | crash | F2 type check | Failed (5/5) |
| 9 | nan_ratings | 7 NaN score fields, violations falsely 0 | F2 strict parsing | Failed (5/5) |
| 10 | nan_equilibrium | R exactly | F2 | Failed (5/5) |
| 11 | infinite_equilibrium | R exactly | F2 | Failed (5/5) |
| 12 | overflow_equilibrium | R exactly (sum overflowed to 0 gaps) | F2 entries in [0, 1], exact sum | Failed (5/5) |
| 13 | negative_equilibrium | R exactly (negatives clipped) | F2 non-negativity | Failed (5/5) |
| 14 | scaled_equilibrium | R exactly (renormalized) | F2 sum must be 1 | Failed (5/5) |
| 15 | zero_equilibrium | crash | F2 | Failed (5/5) |
| 16 | short_equilibrium | crash | F2 shape | Failed (5/5) |
| 17 | rating_inflation | **beat R** (margin 10^6) | F2 consistency, F5 bounded margin | Failed (5/5) |
| 18 | unbounded_margin | **beat R** (margin 10^100) | F2, F5 | Failed (5/5) |
| 19 | infinite_margin | margin +Infinity accepted | F2 strict parsing | Failed (5/5) |
| 20 | string_infinity | margin +Infinity accepted | F2 type check | Failed (5/5) |
| 21 | boolean_ratings | R exactly | F2 booleans rejected | Failed (5/5) |
| 22 | offset_translation | R exactly (centering hid ±10^6) | F5 absolute diff, F2 | Failed (5/5) |
| 23 | mixture_original_drift | R exactly (no drift check) | F5 drift check, F2 | Failed in Shapley, clone, mixture, dominance (where it detects a mixture); offset ties R |
| 24 | clone_no_equilibrium | R exactly | F2 a distribution is required | Failed in Shapley and clone (games with clones); others tie R |
| 25 | clone_arbitrary_ratings | R exactly | F2 consistency | Failed in Shapley and clone; others tie R |
| 26 | short_action_set | R exactly (one counted action) | F4 shapes from the game | Failed (5/5) |
| 27 | empty_action_set | crash | F4, F2 | Failed (5/5) |
| 28 | missing_player | crash | F2 | Failed (5/5) |
| 29 | reverse_dominance_pairs | R exactly (submitted pairs trusted) | F4 pairs from the game, F2 | Failed (5/5) |
| 30 | single_dominance_pair | R exactly | F4, F2 | Failed (5/5) |
| 31 | empty_dominance_pairs | crash | F4 submitted pairs ignored | Ties R (honest method; no gain) |
| 32 | phantom_dominance_action | **beat R** (margin 10^12) | F4 shapes, F2 | Failed (5/5) |
| 33 | zero_mixture_weights | R exactly (weights trusted) | F4 weights fixed; F2: its CCE for an altered game is not one for the real game | Failed in Shapley, clone, mixture, dominance; offset ties R |
| 34 | onehot_mixture | R exactly | F4, F2 | Failed in Shapley, clone, mixture, dominance; offset ties R |
| 35 | extrapolated_mixture | R exactly | F4, F2 | Failed in Shapley, clone, mixture, dominance; offset ties R |
| 36 | rounding | R exactly (4e-9 errors) | none needed: below the 1e-6 tolerance, no gain | Ties R (honest method) |
| 37 | baseline_replace | U; baselines unchanged | F4 baselines in eval | Failed (5/5); baseline rows unchanged |
| 38 | data_replace | worse | F4 `data/` not read | Failed (5/5) |
| 39 | reference_override | U | F4 `reference.json` not read | Failed (5/5) |
| 40 | python_startup | **beat R** (score file rewritten at exit, margin 10^12) | F6 `-I`: hook never loads (no hook marker written) | Failed (5/5) |
| 41 | checkpoint_precedence | **beat R** (margin 10^9 from decoy outputs) | F7 checkpoints never read | Ties R (its rating program is the honest method; decoys ignored) |
| 42 | method_id_collision | R; decoy `zero_rating` results reported | F7; baselines fixed in eval | Ties R; baseline rows unchanged |
| 43 | global_rating_scale | margin 10^6 (better), spreads 1e-8 (worse) | F2 consistency, F5 | Failed (5/5) |
| 44 | masked_nan_ratings | R exactly (NaN hidden by max/min) | F2 strict parsing | Failed (5/5) |
| 45 | masked_nan_strings | R exactly | F2 type check | Failed (5/5) |

New probes against the new contract. They have no "before" because the old test never executed a method.

| # | Probe | What it does | After |
|---|---|---|---|
| 46 | single_lp | First LP of Algorithm 1 only; ratings are the gains at its solution | Below R on 11/11 suites. Official suite: Shapley dev_gap 1.364741 (all-player 4.239106, symmetry 3.641514); clone max_diff 0.172132, all 1.207766; mixture drift 0.406799, error 0.266091; offset 0.09665 |
| 47 | feasibility_cce | Any CCE (zero-objective LP); consistent gains | Below R: Shapley 4.645833 / 5.6875 / 2.958333; clone 0.756767 / 1.267904; mixture 0.654964 / 0.371217; offset 0.878141 |
| 48 | pure_nash | First pure Nash equilibrium, else any CCE | Below R: Shapley 4.645833 / 5.6875 / 2.958333; clone 1.687; mixture 1.596 / 0.842214; offset 1.703 |
| 49 | uniform_gains | Exact deviation gains of the uniform distribution | Failed (5/5): not a CCE |
| 50 | detached_rewriter | Honest method, plus a double-forked `setsid` daemon that rewrites the score file once written | Ties R. The daemon was killed by the evaluator's subreaper before scoring: no rewrite marker, no leftover process |
| 51 | script_append | Honest method, plus appending a score-rewriting command to the running `scripts/evaluate_test.sh` | Ties R. `exec` meant the command never ran (no marker) |

## What I could not fix, stated plainly

- **Ties at the optimum cannot be prevented.** The reference already scores the best possible value (0) on every invariance metric. Any method satisfying the properties ties it, and nothing can beat it, so the gym rewards correctness and robustness rather than headroom.
- **Some other rating methods can tie without running Algorithm 1.** The test checks the paper's properties, not its algorithm. One example: a method that canonicalizes each game (drops clones and mixture actions, normalizes action order, ignores players with constant gains) and then picks a strictest CCE of the reduced game. By construction that satisfies every check. It must still return a real CCE whose deviation gains are its ratings, so I treat it as a legitimate alternative rating rule by the paper's own Table 1 criteria rather than a shortcut. Strictness beyond what these families exercise is not scored.
- **The rating program runs while the hidden test source is on disk.** It has the same file permissions as the evaluator, so it can read `eval/test/evaluate.py` (seed included) and learn which games are transformed copies of which. That only helps the canonicalizing approach above, which can already detect clones, mixtures and offsets from the games themselves: it can tie, not beat. Closing this needs OS-level sandboxing (a separate user, or a read-only namespace without `eval/`), which this environment does not provide.
- **The environment is trusted.** `eval/test` imports only the standard library and runs with `-I`, so `PYTHONPATH`, `sitecustomize.py`, numpy and site-packages cannot reach it. But the container image is built with the agent-editable `environment/setup.sh`, and a modified interpreter or standard library in the image would be out of the evaluator's reach. The hidden test should run in the gym's original container.
- **The subreaper needs Linux `prctl`.** It works in the gym container: probe 50 was killed. Where `prctl` is unavailable the evaluator still kills the rating program's process group, but a double-forked daemon could survive. The audit harness checks for leftover shortcut processes after every replay and found none.
- **Numerical tolerance.** Rating differences up to 1e-6·scale count as 0. A method can add noise below that without penalty, but also without gain (probe 36).
- **Scope** is unchanged: the paper's LiveBench and policy-improvement studies are not scored.

## Reproducing this report

- `bash scripts/run.sh`: reference end to end (paper artifacts, baseline, public evaluation, train, hidden test, `validate.py`).
- `bash redteam/hardening_job.sh`: diagnostics over 11 suites (`redteam/diagnostics.json`), then 3 reference runs and all 51 replays (`redteam/<name>/`, `redteam/shortcut_comparisons.json`).
- Single replay: `bash redteam/<name>/run.sh`.
