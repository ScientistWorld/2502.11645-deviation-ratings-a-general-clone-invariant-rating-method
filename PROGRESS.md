# Progress

## What Works
- The paper's sequential LP deviation-rating algorithm is implemented in [`method/deviation_rating.py`](/home/user/method/deviation_rating.py).
- The packaged reproduction runs end-to-end through [`scripts/reproduce.sh`](/home/user/scripts/reproduce.sh).
- The evaluation pipeline is method-agnostic and lives entirely under [`eval/`](/home/user/eval).
- The current scored experiments reproduce five exact paper-side claims:
  - augmented biased Shapley ratings are equal across `R`, `P`, `S`, and `N`
  - clone invariance holds exactly on a cloned Rock-Paper-Scissors game
  - mixture invariance holds exactly on a scored general-sum reference game
  - offset invariance holds exactly on a scored general-sum reference game
  - dominance preservation holds exactly on a scored dominance test game
- The sequential LP freezes exactly the constraints with nonzero duals, the rule in Section 4.1 of the paper (hardening iteration, 2026-11-07). The intermediate rule that also froze every numerically tight constraint lost uniqueness on degenerate optima and failed the hidden invariance checks; see `HARDENING.md`.

## Results Achieved

Local run on April 7, 2026 via `bash scripts/reproduce.sh`:

| Experiment | Metric | Paper | Reproduced |
|---|---|---:|---:|
| biased_shapley_augmented | dev_gap | 0.0 | 0.0 |
| biased_shapley_augmented | CCE_gap | 0.0 | 0.0 |
| clone_invariance | max_diff | 0.0 | 0.0 |
| mixture_invariance | original_max_diff | 0.0 | 0.0 |
| mixture_invariance | mixture_error | 0.0 | 0.0 |
| offset_invariance | max_diff | 0.0 | 0.0 |
| dominance_preserving | dominance_violations | 0 | 0 |
| dominance_preserving | CCE_gap | 0.0 | 0.0 |

`python validate.py --compare` passes on the current `reference.json` and `scores.json`.

Re-validation on April 7, 2026 confirmed the same outputs immediately before preparing a packaged CPU-only scheduler run through `scripts/run.sh`.

## Final Status
- Current milestone is `secondary_claims`.
- The workspace is packaged as a small research gym centered on five scored theorem/property experiments in `scoring/scores.json`.
- The main remaining limitation is scope, not correctness: the larger empirical sections of the paper, especially the LiveBench-style study, are not packaged into the current benchmark.
- Final verification judged the workspace `partial` for gym use: from-scratch mode is clean and usable, but improve-mode headroom is limited because the current scored metrics are already saturated at their exact optimum.

## Issues Encountered
- Earlier workspace code had solver/sign inconsistencies that broke the small-form paper experiments; these were corrected in the current LP implementation and evaluation setup.
- An intermediate active-set update also froze constraints whose deviation gain numerically matched the optimal `epsilon`. That is not safe: such a constraint may be lowered at another optimal distribution. It was reverted to the paper's nonzero-dual rule. A tight constraint with a zero dual that really is pinned gets frozen in a later iteration at the same value.
- The original status files overstated LiveBench coverage. The packaged environment now reports only experiments that are actually implemented and scored.
- Earlier local verification depended on an ad hoc `/home/user/pkgs` target install. The packaging now follows the required `uv pip install --system` path so scheduler validation will exercise the declared environment rather than leftover login-node state.

## Deviations From Paper
- The current reproduction focuses on exact small normal-form experiments that directly establish the method's strictest-CCE behavior and the paper's invariance and dominance properties.
- The paper's larger LLM evaluation section is not yet part of the scored environment; it remains follow-up work rather than a claimed reproduced result.

## Status
**Milestone: secondary_claims**

The environment is usable: the paper's actual algorithm runs end-to-end, the scored experiments come from executed code, and the reproduced results support both the central clone-invariance claim and additional secondary paper properties on mixture invariance, offset invariance, and dominance preservation. The packaged benchmark is best understood as a correctness-oriented property suite rather than a high-headroom optimization benchmark.

At 2026-04-07 22:22 UTC, the packaged entrypoints were revalidated locally after installing the declared runtime dependencies into `/home/user/pkgs`:
- `bash scripts/reproduce.sh`
- `python3 validate.py --compare`

At 2026-04-24 09:00 UTC, the environment packaging was cleaned up to remove the `/home/user/pkgs` workaround and align with the required `uv pip install --system` workflow before the next scheduler validation run.

At 2026-04-24 09:15 UTC, final verification confirmed the milestone remains `secondary_claims`, generalized [`eval/evaluate.py`](/home/user/eval/evaluate.py) to discover and score arbitrary method output layouts, and removed tracked stale files and the unused OCI tarball that were not part of the shipped gym.

At 2026-04-24 09:06 UTC, the canonical evaluator in [`eval/evaluate.py`](/home/user/eval/evaluate.py) was expanded to score the full declared benchmark contract instead of the earlier reduced subset. `scores.json` now includes the all-player property metrics already declared in `reference.json` and the packaged baselines (`uniform_payoff`, `zero_rating`, and `negative_uniform_payoff`), and `python3 validate.py --compare` still passes after the change.

## Hardening (2026-11-07)

The scored benchmark runs the rating program `scripts/rate.sh` on games supplied by the evaluators, once per population iteration (96 calls).

The hidden test generates about 210 property games and a Sheriff population run at test time. It gates every output: finite, a normalized CCE, and ratings equal to its deviation gains.

Six experiments are scored. The five property experiments now also score `strictness_gap`. The sixth, `population_improvement` (paper Section 5.3), is the headroom experiment.

Reference results:
- **Property experiments:** 0 on every metric, on the hidden test and on 4 further suites.
- **Population (late gap ratio):** reference 0.577, uniform 0.668, random selection 0.968.

`HARDENING.md` lists every shortcut with its score before and after.
