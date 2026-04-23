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
