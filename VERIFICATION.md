# Verification Report

## Initial Assessment

The workspace started in a good state. The reported `secondary_claims` milestone was justified: the paper method was implemented, the canonical evaluator ran, `python3 validate.py --compare` passed, and the theorem-style experiments in `scoring/scores.json` matched the current packaged scope. The remaining work was gym hygiene rather than method repair.

## Issues Found

- Minor: the benchmark-facing documentation lagged behind the current evaluator. [scoring/EXPERIMENTS.md](/home/user/scoring/EXPERIMENTS.md), [scoring/TARGETS.md](/home/user/scoring/TARGETS.md), and parts of [briefing/evaluation.md](/home/user/briefing/evaluation.md) described only the older visible metrics, while the canonical scorer now also uses the added all-player and constraint-side metrics.
- Minor: the current scored benchmark is saturation-prone for improve-mode use. The reproduced method already achieves exact property satisfaction on the small scored games, so this workspace is stronger as a correctness-oriented gym than as an optimization-headroom gym.

## Fixes Applied

- Updated [scoring/EXPERIMENTS.md](/home/user/scoring/EXPERIMENTS.md) so every experiment now lists the full set of scored outputs present in [scoring/scores.json](/home/user/scoring/scores.json).
- Updated [scoring/TARGETS.md](/home/user/scoring/TARGETS.md) so future scientist agents can see the full scored surface, including the added all-player, symmetry, feasibility, and dominance-margin checks.
- Updated [briefing/evaluation.md](/home/user/briefing/evaluation.md) to describe the full evaluation protocol in a method-agnostic way without leaking the paper's solver design.
- Re-ran `python3 validate.py --compare` to confirm the scoring contract still passes after the documentation cleanup.

## Final Judgment

The workspace is structurally clean and honest. A from-scratch scientist can use [briefing/problem.md](/home/user/briefing/problem.md), [briefing/evaluation.md](/home/user/briefing/evaluation.md), [data/](/home/user/data), [eval/](/home/user/eval), and the scoring docs without learning the paper's algorithm. An improve-mode scientist can inspect the full reproduction and rerun it through [scripts/reproduce.sh](/home/user/scripts/reproduce.sh) and [scripts/evaluate.sh](/home/user/scripts/evaluate.sh).

The main limitation is that the scored benchmark currently consists of exact theorem/property checks that the reproduced method already satisfies exactly, so score-improvement headroom is limited. That does not invalidate the current milestone, but it does make this workspace better suited as a correctness-oriented gym than a competitive optimization benchmark.

- Milestone: secondary_claims
- Ready for gym use: partial
- Confidence: high
- Key limitation: scored metrics are saturated exact-property checks, so improve-mode headroom is limited

## Hardening update (2026-11-07)

The evaluation described above has been replaced. The benchmark now scores the rating program `scripts/rate.sh` on public games (train) and on hidden games generated at test time, behind validity gates. The improve-mode limitation still holds: the reference scores exactly 0 on every invariance metric. See `HARDENING.md` and `briefing/evaluation.md`.
