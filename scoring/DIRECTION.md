# Research Direction

## Research Problem

The benchmark studies how to rate strategies in multi-player, general-sum normal-form games when interactions are strategic rather than purely transitive. The core challenge is to produce ratings that remain meaningful when there are cycles, mixed motives, redundant strategies, mixed-strategy extensions, payoff offsets and extra players, and that are useful as a fitness measure for improving a population of strategies.

## Scope

Scientists should work on principled game-theoretic rating methods for normal-form games that preserve the invariance and dominance properties emphasized by the paper. Work that merely fits a scalar ordering to the final benchmark outputs, without modeling the strategic game structure, is out of scope.

## Approach Scope

The scientist may explore:
- Better optimization or numerical methods for computing deviation-style ratings, including on games with a thousand or more joint actions
- Alternative principled equilibrium selections for the same problem family
- Ratings that drive population improvement better while keeping the scored properties
- Broader evaluations after keeping the scored benchmark intact

## How Work Is Measured

A method is judged through the rating program `scripts/rate.sh` on games the evaluators supply, including hidden games generated at test time. Its ratings must be the deviation gains of a coarse correlated equilibrium it returns.

Within that family the scored question is equilibrium selection. Which CCE gives ratings that:
- stay equal on cyclic games;
- stay invariant to clones, mixtures, offsets and extra players;
- are as strict as possible (`strictness_gap`);
- drive a population search toward equilibrium?

The reproduced method scores 0 on every property metric. Measurable progress over it is on `population_improvement`, where it reaches a late gap ratio of about 0.58 on the hidden test and the bound is 0. A gain there that costs strictness or invariance shows up in those metrics.

## Out of Bounds
- Replacing the problem with ordinary pairwise ranking or a non-game-theoretic leaderboard fit
- Using the benchmark's exact numerical targets without recomputation
- Modifying the scored game definitions or metric meanings while still claiming direct improvement on this gym
- Rating programs that read or alter the evaluator, special-case recognizable games, keep state between calls, or leave processes or files behind to affect scoring
