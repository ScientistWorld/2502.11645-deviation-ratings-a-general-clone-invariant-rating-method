# Design Notes: Train/Test Evaluation for Deviation Ratings

## Split Style: Metric Triangulation

This benchmark uses a **metric triangulation** split style rather than a data partition. The rationale:

1. **Small evaluation set**: The benchmark evaluates deviation rating on small normal-form games (2-4 actions per player). Data partitioning would make each slice too small to be meaningful.

2. **Property-based evaluation**: The paper's claims are about theoretical properties (clone invariance, mixture invariance, etc.) rather than statistical performance on a large dataset.

3. **Complementary metrics**: Train measures core equality properties; test measures multi-player symmetry, CCE gap stability, and margin preservation. Both probe the same underlying correctness.

## Metrics

### Train Metrics (core properties)
- `dev_gap`: Maximum rating spread in augmented Shapley game
- `CCE_gap`: Equilibrium quality for Shapley game
- `max_diff`: Clone/mixture/offset invariance violation magnitude
- `original_max_diff`: Mixture invariance violation
- `mixture_error`: Mixed strategy rating inheritance error
- `dominance_violations`: Number of dominance violations

### Test Metrics (complementary)
- `all_player_dev_gap`: Maximum spread across BOTH players (not just player 0)
- `player_symmetry_gap`: Same-action rating mismatch between symmetric players
- `all_players_max_diff`: Clone invariance over ALL players (not just visible slice)
- `clone_source_gap`: Clone/source action rating mismatch
- `max_CCE_gap`: Maximum CCE gap across transformations
- `min_margin`: Smallest dominance margin (positive = correctness)

## Design Decisions

### Why complementary metrics?
A method that "gaming" the train metrics would need to simultaneously:
- Equalize ratings across both players
- Maintain equilibrium quality
- Preserve clone/mixture/offset invariance
- Not violate dominance properties

This is harder to game than a single metric.

### Why near-zero scores?
The deviation rating algorithm achieves exact CCE for these small games, so scores are near 0. This is expected behavior - the test is whether a method ACHIEVES equilibrium, not HOW CLOSE it gets.

## Issues Fixed

1. **Scores files swapped** (fixed): `scores_train.json` had test metrics and vice versa. Swapped to correct assignment.

2. **Score files must not exist at end of designer iteration**: Deleted `scores_train.json` and `scores_test.json` — they are produced later by `evaluate_train.sh` and `evaluate_test.sh`, not by the designer.

## Leakage Analysis

`split_common.py` is at top-level `eval/` (not inside `train/` or `test/`). A future agent reading `eval/train/` sees only the train evaluation code. The shared helper provides only discovery logic and constants — it does not contain test-specific metrics, data, or scoring shape. This is acceptable per the design rules.

## Metrics Coverage

The split uses **metric triangulation** rather than data partition because:
- Small evaluation set (tiny normal-form games)
- Property-based evaluation (invariance theorems, not statistical performance)
- Complementary metrics across train and test

All five experiments have both train and test metrics. The sets are non-overlapping, so gaming train doesn't guarantee good test scores.

## Scripts

- `scripts/evaluate_train.sh`: Runs `eval/train/evaluate.py`, writes `scores_train.json`
- `scripts/evaluate_test.sh`: Runs `eval/test/evaluate.py`, writes `scores_test.json`

Both scripts discover methods from `checkpoints/` and do not have hardcoded method names.
