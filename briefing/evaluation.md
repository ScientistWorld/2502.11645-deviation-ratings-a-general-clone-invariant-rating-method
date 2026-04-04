# Evaluation

How success is measured for a game-theoretic rating method.

## Metrics

Since this is a rating/evaluation method (not a prediction method), evaluation is qualitative and comparative:

1. **Property Verification**: Does the method satisfy its claimed properties?
   - Clone invariance: ratings unchanged after adding strategy clones
   - Mixture invariance: ratings unchanged after adding mixture strategies
   - Offset invariance: ratings unchanged after adding arbitrary payoffs
   - Dominance preserving: dominant strategies rated higher
   - Uniqueness: method always produces unique ratings

2. **Ranking Quality**: How does the method rank strategies compared to baselines?
   - Does it avoid transitive (misleading) rankings in cyclic games?
   - Does it group top performers appropriately?
   - Does it remain stable under population changes?

3. **CCE Gap**: The coarse correlated equilibrium (CCE) gap measures how close the equilibrium distribution is to being stable. Lower is better.

## Baselines and Targets

**Baseline methods** to compare against:
- **Uniform averaging**: mean payoff over all opponents. Simple but not clone invariant.
- **Elo**: only works for 2-player zero-sum. Popular but not clone invariant.
- **Nash averaging**: clone invariant but only for 2-player zero-sum.

**Target properties** (from the paper's Table 1):
- Deviation rating should be the only method satisfying ALL of: dominance preserving, clone invariant, mixture invariant, offset invariant, N-player, general-sum
- The paper's deviation rating on the biased Shapley game should produce equal ratings for all strategies (R=P=S=N)
- On Livebench, deviation rating should group the top 4 models (claude-3-5-sonnet, gemini-1.5-pro, Llama-3.1-405B, gpt-4o) equally at the top

## Evaluation Protocol

### Experiment 1: Biased Shapley Game
- Construct the 4x4 biased Shapley game (R, P, S, plus Nash mixture N)
- Compute uniform ratings and deviation ratings
- Verify deviation rating gives equal ratings to all strategies
- Verify uniform gives transitive ranking R > P > N > S

### Experiment 2: Clone Invariance Test
- Take a Rock-Paper-Scissors game
- Compute deviation ratings for original game
- Add a clone of one strategy and recompute
- Verify ratings of original strategies are unchanged

### Experiment 3: LLM Rating on Livebench
- Construct 3-player game from model-task scores
- Compute deviation ratings
- Verify top 4 models are grouped at the top

### Experiment 4: Property Table
- Verify all properties in the paper's Table 1 hold for deviation rating
