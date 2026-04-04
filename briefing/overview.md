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
