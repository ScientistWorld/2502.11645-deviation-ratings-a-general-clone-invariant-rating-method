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
- **Be efficiently computable**: polynomial time in the size of the game, and practical on games with a thousand or more joint strategies
- **Be directional**: when a rating is used to decide which strategies to keep in an evolving population, the population should move toward an equilibrium of the underlying game rather than toward strategies that only look good on average
- **Hold up on measured data**: evaluation payoffs are estimates (a model's score on a task comes from finitely many prompts), and redundant strategies are near-copies rather than exact clones. Ratings computed from noisy data that contain near-copies should stay close to the ratings of the true game
