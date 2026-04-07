# Evaluation

How success is measured for a game-theoretic rating method.

## Metrics

Since this is a rating task rather than a supervised prediction task, evaluation is based on whether a method produces stable and interpretable ratings on explicit normal-form games that expose the benchmark's key phenomena.

1. **Deviation equality on the augmented biased Shapley game**
   - A successful method should assign equal ratings to `R`, `P`, `S`, and the added mixed action `N`
   - The selected recommendation distribution should satisfy the benchmark's equilibrium-feasibility check (`CCE_gap = 0`)

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
- The method should avoid imposing an artificial linear order on the augmented biased Shapley example
- The method should be invariant to duplicated strategies on the cloned-RPS example
- The selected recommendation distribution should satisfy the equilibrium-feasibility check (`CCE_gap = 0`)

## Evaluation Protocol

### Experiment 1: Biased Shapley Game
- Construct the 4x4 biased Shapley game (R, P, S, plus Nash mixture N)
- Compute ratings and compare all four action ratings
- Score `dev_gap = max(ratings) - min(ratings)` and `CCE_gap`

### Experiment 2: Clone Invariance Test
- Take a Rock-Paper-Scissors game
- Compute ratings for the original game
- Add a clone of one strategy and recompute
- Score `max_diff` over the original strategies' ratings before vs. after cloning

## Packaged Scope

The paper also contains broader theoretical and empirical claims, including larger benchmark analyses. The current reusable environment packages the minimum experiments needed for `core_claim`: the augmented biased Shapley example and clone invariance.
