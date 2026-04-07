# Evaluation

How success is measured for a game-theoretic rating method.

## Metrics

Since this is a rating method rather than a supervised predictor, evaluation is based on whether the computed ratings satisfy the paper's game-theoretic claims on explicit normal-form games.

1. **Deviation equality on the augmented biased Shapley game**
   - The paper's method should assign equal deviation ratings to `R`, `P`, `S`, and the Nash-mixture action `N`
   - The strictest-CCE solution should have zero residual deviation gain (`CCE_gap = 0`)

2. **Clone invariance**
   - If one strategy is duplicated, the ratings assigned to the original strategies should remain unchanged
   - The scored statistic is the maximum absolute difference between original-game ratings and cloned-game ratings (`max_diff`)

3. **Baseline contrast**
   - A simple uniform-payoff baseline is included to demonstrate that naive averaging need not satisfy the same invariance/equality behavior
   - Baselines are evaluated through the same reusable evaluation pipeline

## Baselines and Targets

**Baseline methods** used in the packaged environment:
- **Uniform averaging**: mean payoff over all opponents. Simple but not clone invariant.

**Target properties** reflected by the current scored experiments:
- Deviation rating should produce equal ratings on the augmented biased Shapley example
- Deviation rating should be clone invariant on the cloned-RPS example
- The equilibrium found by the LP should satisfy the paper's strictest-CCE conditions (`CCE_gap = 0`)

## Evaluation Protocol

### Experiment 1: Biased Shapley Game
- Construct the 4x4 biased Shapley game (R, P, S, plus Nash mixture N)
- Compute deviation ratings and compare all four action ratings
- Score `dev_gap = max(ratings) - min(ratings)` and `CCE_gap`

### Experiment 2: Clone Invariance Test
- Take a Rock-Paper-Scissors game
- Compute deviation ratings for original game
- Add a clone of one strategy and recompute
- Score `max_diff` over the original strategies' ratings before vs. after cloning

## Packaged Scope

The paper also contains broader theoretical and empirical claims, including the model/task rating example. The current reusable environment packages the minimum experiments needed for `core_claim`: the augmented biased Shapley example and clone invariance.
