# Overview

- **Paper ID:** 2502.11645
- **Title:** Deviation Ratings: A General, Clone Invariant Rating Method
- **Domain:** Game Theory / Multi-Agent Systems / LLM Evaluation
- **TL;DR:** Introduces deviation ratings — the first N-player general-sum game-theoretic rating method that is clone-invariant (adding duplicate strategies doesn't change ratings), enabling scalable and manipulation-resistant evaluation of LLMs, RL agents, and other strategies.

## Short Summary

The paper addresses the problem of rating strategies in multi-agent and multi-task evaluation scenarios. Existing rating methods (Elo, Nash averaging) have a key weakness: they are either limited to two-player zero-sum games or not clone-invariant. Clone invariance means that adding a copy of an existing strategy doesn't change anyone's rating — a crucial property for scalable, manipulation-resistant evaluation.

Deviation ratings solve this by computing ratings from coarse correlated equilibria (CCE) using a novel sequential linear programming approach. Instead of selecting an equilibrium and extracting ratings, the method directly minimizes the maximum deviation gain across all strategies, which uniquely determines the ratings. The method is the first to achieve clone invariance for the full class of N-player general-sum normal-form games.

## Key Results

- Deviation rating is the only method satisfying ALL of: clone invariance, mixture invariance, offset invariance, dominance preserving, N-player, and general-sum (Table 1)
- On the biased Shapley game, deviation rating correctly gives equal ratings to all strategies in a cycle, while uniform averaging produces a misleading transitive ranking
- On Livebench (18 LLMs × 18 tasks), deviation rating groups the top 4 models (claude-3-5-sonnet, gemini-1.5-pro, Llama-3.1-405B, gpt-4o) at the top — reflecting that each excels in different niches
- The method is computationally efficient: polynomial time via sequential linear programming using CVXPY + GLOP

---

# Problem Definition

How do you rate strategies (players, models, agents, tasks) in multi-agent or multi-task evaluation scenarios where interactions are strategic — adversarial, cooperative, or mixed-motive?

## Research Question

When you have outcomes from pairwise (or multi-way) interactions — win/loss records, scores, ratings — how do you distill these into a single quality score per strategy that:

1. **Is clone invariant**: adding a copy (clone) of an existing strategy does not change anyone's rating
2. **Is scalable**: redundant or overlapping data should not distort ratings without manual curation
3. **Is resilient**: cannot be manipulated by submitting many similar strategies that exploit a niche
4. **Is directional**: optimizing the rating leads to genuine improvement
5. **Works for N players and general-sum games**: not limited to two-player zero-sum

This is known as the **strategy rating problem** in game theory.

## Why It Matters

Real-world evaluation scenarios naturally model as normal-form games:
- **LLM leaderboards** (Chatbot Arena): model vs model vs prompt — a 3-player general-sum game
- **RL agent benchmarks**: agent vs task — where different tasks measure overlapping skills
- **Sports rankings**: team vs team — but the same team can appear in many contexts
- **Chess ratings**: player vs player — but with transitive and intransitive cycles

Existing methods (Elo, TrueSkill, etc.) only work for two-player zero-sum games. Other methods like Nash averaging achieve clone invariance but are limited to two-player zero-sum. No existing method achieves clone invariance for N-player general-sum games.

## Success Criteria

A rating method should:
- Produce **unique** ratings that always exist for any finite game
- **Preserve dominance**: if strategy A dominates B (never worse, sometimes better), A must be rated higher
- **Be clone invariant**: copying strategies doesn't change any ratings
- **Be mixture invariant**: adding mixtures of existing strategies doesn't change ratings
- **Be offset invariant**: adding arbitrary offsets to payoffs doesn't change ratings
- **Scale to N players and general-sum games**: no restrictions on number of players or payoff structure
- **Be efficiently computable**: polynomial time in the size of the game

---

# Paper's Method: Deviation Rating

## Key Contribution

The paper introduces **deviation rating** — the first N-player general-sum clone-invariant rating method. Previous clone-invariant methods (Nash averaging) were limited to two-player zero-sum games. Deviation rating achieves clone invariance for the most general class of normal-form games by using coarse correlated equilibria (CCE) instead of Nash equilibrium.

## Approach

### Core Insight

Instead of computing an equilibrium and extracting ratings from it (which requires equilibrium selection — a hard problem in N-player games), the method selects deviation gains directly. The deviation gain of strategy $a'_p$ measures how much payoff player $p$ gains by deviating to $a'_p$ from the equilibrium distribution.

The rating is defined as the **deviation gain at the strictest CCE** (Equation 4):

$$r_p^{CCE}(a'_p) = \sum_a \sigma^*(a) [G_p(a'_p, a_{-p}) - G_p(a)]$$

where $\sigma^*$ is the CCE distribution that minimizes the maximum deviation gain.

### Algorithm 1: CCE Deviation Rating

The algorithm works iteratively:

1. Start with no frozen constraints (no rated strategies)
2. Each iteration solves an LP:
   - Minimize the maximum deviation gain $\epsilon$
   - Subject to: $\sigma$ is a probability distribution, and for each already-rated strategy $(p, a'_p)$: its deviation gain equals its frozen rating
3. From the LP solution, identify which deviation gain constraints are active (at the optimum)
4. Freeze those constraints (add them to the active set) with their computed ratings
5. Repeat until all strategies are rated

The LP finds the **strictest CCE** — the equilibrium where no player can gain the most by deviating. Since ratings are derived from the objective value (not the solution parameters), the ratings are unique even though many equilibria may exist.

### Computational Approach

The LP uses CVXPY with GLOP (OR-Tools' simplex solver) as the backend. The algorithm runs in polynomial time since it solves sequential LPs, each in polynomial time. The maximum number of outer iterations is $\sum_p |A_p|$ (number of constraints).

## Main Claims

**Primary**: Deviation rating is the first N-player general-sum clone-invariant rating method.

**Properties** (proven in the paper, Table 1):
- Existence: always exists (CCE always exists)
- Uniqueness: always produces unique ratings
- Clone invariant: copying strategies doesn't change ratings
- Mixture invariant: adding mixtures doesn't change ratings
- Offset invariant: adding arbitrary offsets doesn't change ratings
- Dominance preserving: dominant strategies rated higher
- N-player general-sum: no restrictions

**Secondary**: On cyclic games (Shapley's game), deviation rating gives equal ratings to all strategies in the cycle. On LLM evaluation (Livebench), deviation rating groups top models by niche rather than forcing a linear ranking.

---

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

---

# Reproduction Milestones

**Current: method_runs**

## Progress Log

### [2026-04-05] - method_runs
- Implemented deviation rating algorithm (Algorithm 1) in method/deviation_rating.py
- Fixed game construction: biased Shapley game is 3×3 (R,P,S only — the cycle game)
- All experiments implemented: Shapley game, clone invariance, Livebench LLM rating, population study
- Fixed scores.json format to only include numeric metrics matching reference.json
- SCS solver with improved convergence parameters
- Previous test: algorithm runs, Livebench works (top4_overlap=4/4), but Shapley game needs CCE_gap=0

### [2026-04-04] - none
- Initial workspace setup
- Read the paper thoroughly
