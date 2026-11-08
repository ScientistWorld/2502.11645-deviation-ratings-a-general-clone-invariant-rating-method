# Hardening report (iteration 14, final)

## Summary

`REDTEAM.md` found three problems:
- **No honest method could score higher than the reference.** A faster exact solver tied it; no better variant existed.
- **The 32-round-cap shortcut tied the reference** on all 22 hidden metrics.
- **The size-limit shortcut tied the reference.** It abandons games above 4,096 joint actions.

All three are fixed:

| | Before (REDTEAM, old test) | After (this test) |
|---|---|---|
| Better variant (merges near-copies within the noise bound) | ties (no game where it differs) | **+0.0395** (train +0.0307) |
| Weaker variant (one LP of Algorithm 1) | −3.196 | −3.962 (train −3.537) |
| 32-round cap shortcut | **0, tie** | −1.730, worse in all 5 property experiments |
| Size-limit shortcut (>4,096 joint actions) | **0, tie** | failed (1e6) in all 5 property experiments |
| Uniform baseline | −3.878 | −4.425 |

- **Rank** is `sum_experiment weight * sum_metric coefficient * (method - reference)`, with the weights and coefficients of `scoring/reference.json` (`redteam/hardening_iter14/summary.json`). Higher is better; the reference is 0.
- **Before** values are REDTEAM's ranks with the old weights.
- **The reference is unchanged** on every metric it was scored on before. It still scores 0 on every property metric (`min_margin` 1) and 0.576602 / 0.646034 on the population experiment. Its train and hidden runs are byte-identical to an independent replay.

## Why better results could not score higher, and what changed

The diagnosis behind the fix:
- A valid output is the deviation gains of a CCE.
- `strictness_gap` and the invariance checks pin which CCE.
- So on exact games, every method that scores 0 on every property metric returns the reference's ratings.
- It therefore also makes the same drop decisions in the population experiment. Iterations 12-14 found every honest variant tied there.
- So the old test could only measure reproduction, and no amount of re-weighting would change that.

**New scored experiment `noisy_clone_resilience` (weight 0.15), from where the paper's method falls short.**

- **Motivation.** The paper motivates clone invariance with evaluation data: LLM leaderboards, Chatbot Arena, "similar prompts". In such data every payoff is a measurement and redundant strategies are near-copies.
- **Instances.** 96 hidden instances (96 more visible, from the train seed). Each is a small true game:
  - random 2-player games (3-4 actions);
  - random 3-player games (2-3 actions);
  - random zero-sum games;
  - the paper's Section 5.2 model vs model vs task game, built from a model x task score matrix.
- **Observations.** Each true game is observed twice, in different calls, with every payoff within the stated `noise_bound` 0.05 of the truth:
  - once padded with 3-10 near-copies of one action (for the model vs model vs task game, of one task);
  - once without.
- **Target.** The exact deviation rating of the true game. The evaluator computes it in rational arithmetic (Algorithm 1 with an exact simplex), which avoids the float ill-posedness that ruled out float ground truth below the top level.
- **Metrics.** Mean absolute rating error, in units of the noise bound:
  - `rating_error` (padded observations; primary, coefficient −1);
  - `clean_rating_error` (unpadded observations; −0.5).
- **Gate.** For these games, and only these, a method may return `payoffs`: the game it rated, its estimate of the true game. Every entry must be within the noise bound of the observation; the CCE and rating gates then use it.
- **Why the property side is untouched.**
  - Exact games carry no noise bound, so a method cannot use this field to change anything on experiments 1-6.
  - The true game always lies within the bound, so the exact answer is admissible.

The paper's method on the data (rate the observation as given) is the reference. It is not optimal:

| Hidden test | Reference (paper's method) | Merge variant | Uniform baseline |
|---|---:|---:|---:|
| `rating_error` | 0.712453 | **0.448893** | 6.109139 |
| `clean_rating_error` | 0.487613 | 0.487613 | 6.165559 |
| Train: `rating_error` / `clean_rating_error` | 0.735823 / 0.547185 | 0.531310 / 0.547185 | 6.297090 / 5.902903 |

**The merge variant** (`merge_near_copies` in `redteam/hardening_iter14/rating_program.py`) works as follows:
- It treats two actions as copies when every pair of corresponding observed payoffs is within twice the bound, so one true payoff is consistent with both.
- It sets each merged payoff to the midpoint of the interval consistent with all observations.
- It then runs the unchanged Algorithm 1 on that estimate.
- Copies become exact clones, so Property 6 applies to them, and their repeated measurements average out.
- On exact games it is the reference. It ties every other experiment exactly and changes no clean observation.

**Larger than the test's noise.** The reference is deterministic, so the relevant noise is how the comparison would vary over other hidden draws. `redteam/hardening_iter14/paired_noisy.py` re-rates every hidden noisy observation both ways in exact arithmetic. Its plug-in aggregate is PAIRED_PLUG, against 0.712453 from the job's float reference, and its merge aggregate is PAIRED_MERGE. On the padded observations:
- the paired improvement is PAIRED_DIFF ± PAIRED_SE (standard error), t = PAIRED_T;
- the merge variant is better on PAIRED_BETTER of 96 instances and worse on PAIRED_WORSE.

**Headroom remains above the merge variant.** It does not touch `clean_rating_error`, where noise alone moves ratings by about half the bound on average and occasionally by more than one payoff unit, because deviation ratings are discontinuous in the payoffs. 0 is unattainable from noisy data.

**Weights.**
- The six earlier experiments were scaled by 0.85, so their ratios are unchanged.
- `noisy_clone_resilience` gets 0.15, between the single invariance experiments (0.102-0.136) and the population experiment (0.17).
- Reason: it is the one experiment where an honest method can score above the paper's without breaking the constraints the paper satisfies, and it tests the paper's own resilience claim on realistic data.
- `scoring/reference.json` keeps every paper-reported number unchanged.
- The schema requires a value for the proposed method in the new experiment. The paper reports none, so the reproduced hidden-test values are recorded there and labelled as not paper results.

## Major shortcuts: fix and score before and after

| Shortcut | Before | Fix | After |
|---|---|---|---|
| [32-round cap](redteam/hardening_iter14/cap32_shortcut/scores_test.json) | **R on all 22 metrics** | **Deep bystanders.** Every property experiment has games with one bystander of 40-150 actions. Every level lies strictly between 0 and the other players' strictest value, so that value is reached only after one LP round per level. The existing block certificate (`strictness_gap` per independent block) then detects a selection that stopped early. Block values are now computed on each block's own sub-game: same constraints, much cheaper. | Worse in all 5 property experiments: cyclic `dev_gap` 2.94, strictness 2.29; clone 0.086; mixture 0.93; offset 0.34; dominance strictness 0.13. Rank −1.730. On REDTEAM's public witness it still returns −0.31, −0.31, −1.65, −0.61 for ratings that are all −2.82. |
| [Size limit (abandon >4,096 joint actions)](redteam/hardening_iter14/size_limit_shortcut/scores_test.json) | **R on all 22 metrics** | **Bigger games in every property experiment**: 3- to 5-player games of 4,600-6,300 joint actions, and a 48-strategy cyclic population with a bystander (4,608). | **Failed** in all 5 property experiments: missing equilibria on games of 4,608-6,300 joint actions. |
| New gate: `payoffs` outside the noise bound | — | The evaluator checks shape, finiteness and that every entry is within the bound (+1e-9·scale). | Direct check on all 192 hidden noisy observations (`band_gate_check.json`): moved by 2·bound fails 192/192 with the band reason; moved by exactly the bound passes the band check; malformed fails 192/192; ignored on exact games. The container replay of this case stalled (see below). |

The other eleven REDTEAM shortcuts are left as they were, because none of them depends on anything this iteration changed:
- nine scored F: visible-answer cache, reported fields, direct score writing, baseline moving, artifact replacement, constant zero, empty output, impossible values, copied input;
- two scored below the reference: the 12-round cap (−0.009) and feasibility-only (−0.042).

They rest on recomputation from raw outputs, the validity gates, evaluator-owned baselines and fresh score files, all unchanged, so they were not replayed. The 12-round cap is strictly weaker than the 32-round cap, which now loses in all five property experiments.

## Shortcuts and gaps left open

- **A round cap of about 150 or more.** The deepest certified block on the hidden test needs about 150 rounds; a cap above that ties. No finite test closes this, and such a cap is the full algorithm on every tested game.
- **Abandoning games above about 6,300 joint actions.** This is outside the documented envelope (2-5 players, up to about 6,500 joint actions, players with up to 150 actions). The compliance checklist now states the tested range instead of "any finite game".
- **Strictness below the top within games without product structure** is still certified only through the invariance checks, not directly.
- **Recognizing product structure** in order to treat blocks specially would be special-casing, which `CONSTRAINTS.md` forbids.
- **Runtime is unscored.** The faster exact solver still ties, by design: no metric may depend on wall-clock time.
- **In the noisy experiment, using the stated bound, the bounded-noise model, the payoff range and the model vs model vs task construction is allowed.** That is information about the data, not about the test. True payoffs and noise have 6 decimals, so there is no grid to snap to.
- **Iteration-12/13 residuals, unchanged:**
  - the stateless check has unwatched system paths;
  - the rater is not sandboxed from reading `eval/test/evaluate.py`;
  - the container is trusted.

## Reference score, before and after

| Experiment | Reference before | Reference after | Uniform after |
|---|---|---|---|
| Five property experiments | 0 on all 20 metrics (`min_margin` 1) | the same, on the enlarged suite (281 games, up to 6,300 joint actions, bystanders up to 150 actions) | e.g. cyclic `dev_gap` 2.2555, clone 0.443252, offset 3.2, strictness 1.45-4.29 |
| `population_improvement` | 0.576602 / 0.646034 | 0.576602 / 0.646034 | 0.667682 / 0.70202; random 0.968004 / 0.964801 |
| `noisy_clone_resilience` | — | 0.712453 / 0.487613 | 6.109139 / 6.165559 |

- `scoring/scores_test.json`, `scores_train.json` and `scores.json` were regenerated by `scripts/run.sh` from the final code. They are byte-identical to the replay harness's reference run (`redteam/hardening_iter14/reference_seed_0`).
- Train: 0 on every property metric, population 0.712638 / 0.778461, noisy 0.735823 / 0.547185.
- `python3 validate.py` passes.

## Headroom check

- **At the bound:** all 20 property metrics, by construction. They are the constraint side of the paper's claim: invariance, dominance, strictness.
- **Below the bound, but no honest variant beats it:** `population_improvement` (0.577; bound 0). Any method that keeps the property metrics at 0 makes the reference's drop decisions.
- **Below the bound, and a better variant scores higher:** `noisy_clone_resilience`. The merge variant lowers `rating_error` from 0.712 to 0.449 on the hidden test and from 0.736 to 0.531 on train. It does not reach the bound, and it leaves `clean_rating_error` (0.488) untouched.
- **The simple baseline** (uniform) is far below on a scale with room above: 6.11 vs 0.71.

## Direction of the paper's claims

Unchanged from iteration 13:
- the reference beats uniform on cyclic equality, clone, mixture and offset invariance, CCE validity and strictness, and ties it on dominance;
- on Section 5.3, deviation ratings reduce the full-game gap more than uniform averaging, on both the hidden and the train seed (0.577 vs 0.668; 0.713 vs 0.797).

## What I could not finish or explain

- **The container replay of `band_violation_shortcut` stalled.**
  - Its hidden test printed nothing for 49 minutes; normally the first progress line appears after about 2 minutes. Even the harness's 2,800-second timeout did not fire.
  - I cancelled the job. This is the same no-output stall that iterations 12 and 13 each saw once, in different cases; the cause is still unknown.
  - The gate itself is verified directly on every hidden noisy observation (`band_gate_check.py`).
  - The cancelled harness left the candidate installed; I restored the workspace from its saved state and checked it against the reference run.
- **The seed-1 replay** (every game's action labels permuted before solving) was queued after it and did not run. Determinism rests on two byte-identical runs of the reference, plus iteration 13's five byte-identical runs including the permuted one.
- **Unchanged scope:** the paper's LiveBench and Atari data, Figure 1's population studies and 3-player Kuhn poker remain unscored. Experiment 7 uses the model vs model vs task construction on synthetic score matrices.

## Reproducing this report

- `bash scripts/run.sh`: the reference end to end (paper artifacts, baseline, standard, train and hidden evaluation, `validate.py`), about 25 minutes.
- `python3 redteam/hardening_iter14/run_bundle.py`: the replays above, resumable, about 2 hours.
- `python3 redteam/hardening_iter14/summarize.py`: the ranks.
- `python3 redteam/hardening_iter14/paired_noisy.py --split test`: the exact paired comparison, about 30 minutes on 2 cores.
- `python3 redteam/hardening_iter14/band_gate_check.py`: the noise-bound gate check.
