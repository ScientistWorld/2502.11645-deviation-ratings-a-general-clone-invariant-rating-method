# Progress

## What Works
- The paper's sequential LP deviation-rating algorithm is implemented in [`method/deviation_rating.py`](/home/user/method/deviation_rating.py).
- The packaged reproduction runs end-to-end through [`scripts/reproduce.sh`](/home/user/scripts/reproduce.sh).
- The evaluation pipeline is method-agnostic and lives entirely under [`eval/`](/home/user/eval).
- The current scored experiments reproduce two exact paper-side claims:
  - augmented biased Shapley ratings are equal across `R`, `P`, `S`, and `N`
  - clone invariance holds exactly on a cloned Rock-Paper-Scissors game

## Results Achieved

Local run on April 7, 2026 via `bash scripts/reproduce.sh`:

| Experiment | Metric | Paper | Reproduced |
|---|---|---:|---:|
| biased_shapley_augmented | dev_gap | 0.0 | 0.0 |
| biased_shapley_augmented | CCE_gap | 0.0 | 0.0 |
| clone_invariance | max_diff | 0.0 | 0.0 |

`python validate.py --compare` passes on the current `reference.json` and `scores.json`.

Re-validation on April 7, 2026 confirmed the same outputs immediately before submitting a packaged CPU-only scheduler run through `scripts/run.sh`.

## Final Status
- Final milestone remains `core_claim`.
- The workspace is packaged as a small research gym centered on the two scored experiments in `scoring/scores.json`.
- No further work is planned in this paper session.
- The main remaining limitation is scope, not correctness: the larger empirical sections of the paper are not packaged into the current benchmark.

## Issues Encountered
- Earlier workspace code had solver/sign inconsistencies that broke the small-form paper experiments; these were corrected in the current LP implementation and evaluation setup.
- The original status files overstated LiveBench coverage. The packaged environment now reports only experiments that are actually implemented and scored.
- The login node did not yet have `/home/user/pkgs`, so `numpy` and `scipy` were not importable until the dependencies declared in `environment/setup.sh` were installed into that path for local verification.

## Deviations From Paper
- The current `core_claim` reproduction focuses on the exact small normal-form experiments that directly establish the method's strictest-CCE behavior and clone invariance.
- The paper's larger LLM evaluation section is not yet part of the scored environment; it remains follow-up work rather than a claimed reproduced result.

## Status
**Milestone: core_claim**

The environment is usable: the paper's actual algorithm runs end-to-end, the scored experiments come from executed code, and the minimum reproduced results support the central claim that deviation ratings yield clone-invariant ratings in general normal-form settings.

At 2026-04-07 22:22 UTC, the packaged entrypoints were revalidated locally after installing the declared runtime dependencies into `/home/user/pkgs`:
- `bash scripts/reproduce.sh`
- `python3 validate.py --compare`
