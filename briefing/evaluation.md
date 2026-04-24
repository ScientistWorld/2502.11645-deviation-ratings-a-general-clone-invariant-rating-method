# Evaluation

How success is measured for a game-theoretic rating method.

## Metrics

Since this is a rating task rather than a supervised prediction task, evaluation is based on whether a method produces stable and interpretable ratings on explicit normal-form games that expose the benchmark's key phenomena.

1. **Deviation equality on the augmented biased Shapley game**
   - A successful method should assign equal ratings to `R`, `P`, `S`, and the added mixed action `N`
   - The selected recommendation distribution should satisfy the benchmark's equilibrium-feasibility check (`CCE_gap = 0`)
   - The equality check is also verified across both players and corresponding symmetric actions

2. **Clone invariance**
   - If one strategy is duplicated, the ratings assigned to the original strategies should remain unchanged
   - The scored statistics check both the visible original slice and the full two-player game, and also verify that the clone matches its source action

3. **Mixture invariance**
   - If a mixed strategy is added to a game, the original ratings should remain unchanged
   - The new strategy's rating should equal the corresponding mixture of the original ratings
   - The benchmark also checks equilibrium-feasibility on both the base and augmented games

4. **Offset invariance**
   - Adding arbitrary offsets that depend only on the opponents' actions should not change ratings
   - The benchmark also checks equilibrium-feasibility on both the base and offset-transformed games

5. **Dominance preservation**
   - If one strategy dominates another, it should not receive a lower rating
   - The benchmark records both the number of violated dominance relations and the smallest remaining dominance margin

6. **Baseline contrast**
   - A simple uniform-payoff baseline is included to demonstrate that naive averaging need not satisfy the same invariance/equality behavior
   - Baselines are evaluated through the same reusable evaluation pipeline

## Baselines and Targets

**Baseline methods** used in the packaged environment:
- **Uniform averaging**: mean payoff over all opponents. Simple but not clone invariant.

**Target properties** reflected by the current scored experiments:
- The method should avoid imposing an artificial linear order on the augmented biased Shapley example
- The method should be invariant to duplicated strategies on the cloned-RPS example
- The method should be invariant to mixed-strategy augmentation on a scored general-sum reference game
- The method should be invariant to payoff offsets on a scored general-sum reference game
- The method should preserve encoded dominance relations on a scored dominance test game
- The selected recommendation distribution should satisfy the equilibrium-feasibility check (`CCE_gap = 0`)

## Evaluation Protocol

### Experiment 1: Biased Shapley Game
- Construct the 4x4 biased Shapley game (R, P, S, plus Nash mixture N)
- Compute ratings and compare all four action ratings
- Score the visible action spread, the all-player action spread, the cross-player symmetry gap, and `CCE_gap`

### Experiment 2: Clone Invariance Test
- Take a Rock-Paper-Scissors game
- Compute ratings for the original game
- Add a clone of one strategy and recompute
- Score the visible original-slice difference, the all-player difference, and the clone-source mismatch

### Experiment 3: Mixture Invariance Test
- Start from a small general-sum 2x2 game with non-equal ratings
- Add one mixed strategy for player 0
- Score the maximum change in original ratings, the error between the new rating and the expected mixed rating, and the worst equilibrium-feasibility gap across the base and augmented games

### Experiment 4: Offset Invariance Test
- Start from the same small general-sum 2x2 game
- Add arbitrary `b_p(a_-p)` offsets to each player's payoffs
- Score `max_diff` between the original and offset-adjusted ratings and the worst equilibrium-feasibility gap across the base and offset-adjusted games

### Experiment 5: Dominance Preservation Test
- Evaluate a 2x2 game with one strictly dominant action per player
- Score how many encoded dominance relations are violated, the smallest dominance margin, and the equilibrium-feasibility gap

## Packaged Scope

The paper also contains broader empirical claims, including LiveBench and policy-improvement studies. The current reusable environment packages the exact small-game experiments that cover the core theorem-style claims and several secondary properties at low cost.
