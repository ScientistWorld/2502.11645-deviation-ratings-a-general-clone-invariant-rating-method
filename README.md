# Deviation Ratings: A General, Clone-Invariant Rating Method

| This paper | Scientist World, the framework this environment belongs to |
|:---:|:---:|
| <a href="https://arxiv.org/abs/2502.11645"><img alt="This paper on arXiv" src="https://img.shields.io/badge/arXiv-2502.11645-b31b1b?logo=arxiv&logoColor=white"></a> | <a href="https://arxiv.org/abs/2611.08478"><img alt="Scientist World on arXiv" src="https://img.shields.io/badge/arXiv-2611.08478-b31b1b?logo=arxiv&logoColor=white"></a> <a href="https://github.com/zlab-princeton/scientist_world"><img alt="Scientist World code" src="https://img.shields.io/badge/Code-Scientist_World-181717?logo=github&logoColor=white"></a> <a href="https://github.com/zlab-princeton/scientist_world_cli"><img alt="Command line code" src="https://img.shields.io/badge/Code-Command_line-181717?logo=github&logoColor=white"></a> |

| | |
|---|---|
| **Paper ID** | [2502.11645](https://arxiv.org/abs/2502.11645) |
| **Domain** | Game Theory / Multi-Agent Systems / LLM Evaluation |
| **TL;DR** | Introduces deviation ratings — the first N-player general-sum game-theoretic rating method that is clone-invariant (adding duplicate strategies doesn't change ratings), enabling scalable and manipulation-resistant evaluation of LLMs, RL agents, and other strategies. |

## Summary

The paper addresses the problem of rating strategies in multi-agent and multi-task evaluation scenarios. Existing rating methods (Elo, Nash averaging) have a key weakness: they are either limited to two-player zero-sum games or not clone-invariant. Clone invariance means that adding a copy of an existing strategy doesn't change anyone's rating — a crucial property for scalable, manipulation-resistant evaluation.

Deviation ratings solve this by computing ratings from coarse correlated equilibria (CCE) using a novel sequential linear programming approach. Instead of selecting an equilibrium and extracting ratings, the method directly minimizes the maximum deviation gain across all strategies, which uniquely determines the ratings. The method is the first to achieve clone invariance for the full class of N-player general-sum normal-form games.

## Problem

When you have outcomes from pairwise (or multi-way) interactions — win/loss records, scores, ratings — how do you distill these into a single quality score per strategy that:

1. **Is clone invariant**: adding a copy (clone) of an existing strategy does not change anyone's rating
2. **Is scalable**: redundant or overlapping data should not distort ratings without manual curation
3. **Is resilient**: cannot be manipulated by submitting many similar strategies that exploit a niche
4. **Is directional**: optimizing the rating leads to genuine improvement
5. **Works for N players and general-sum games**: not limited to two-player zero-sum

This is known as the **strategy rating problem** in game theory.

## The paper's method

The paper introduces **deviation rating** — the first N-player general-sum clone-invariant rating method. Previous clone-invariant methods (Nash averaging) were limited to two-player zero-sum games. Deviation rating achieves clone invariance for the most general class of normal-form games by using coarse correlated equilibria (CCE) instead of Nash equilibrium.

## Key results of the paper

- Deviation rating is the only method satisfying ALL of: clone invariance, mixture invariance, offset invariance, dominance preserving, N-player, and general-sum (Table 1)
- On the biased Shapley game, deviation rating correctly gives equal ratings to all strategies in a cycle, while uniform averaging produces a misleading transitive ranking
- On Livebench (18 LLMs × 18 tasks), deviation rating groups the top 4 models (claude-3-5-sonnet, gemini-1.5-pro, Llama-3.1-405B, gpt-4o) at the top — reflecting that each excels in different niches
- The method is computationally efficient: polynomial time via sequential linear programming using CVXPY + GLOP

## Run it

```bash
pip install sciworld
sw research 2502.11645 --mode innovate --agent claude-code
sw evaluate 2502.11645
```

## More

The full problem statement, method notes, evaluation protocol and reproduction log are in [DETAILS.md](DETAILS.md).

