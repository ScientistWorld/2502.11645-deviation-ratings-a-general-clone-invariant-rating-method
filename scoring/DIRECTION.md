# Research Direction

## Research Problem

The benchmark studies how to rate strategies in multi-player, general-sum normal-form games when interactions are strategic rather than purely transitive. The core challenge is to produce ratings that remain meaningful when there are cycles, mixed motives, redundant strategies, mixed-strategy extensions, and payoff offsets.

## Scope

Scientists should work on principled game-theoretic rating methods for normal-form games that preserve the invariance and dominance properties emphasized by the paper. Work that merely fits a scalar ordering to the final benchmark outputs, without modeling the strategic game structure, is out of scope.

## Approach Scope

The scientist may explore:
- Better optimization or numerical methods for computing deviation-style ratings
- Alternative principled rating formulations for the same problem family
- Improved scalability to larger games while preserving the scored properties
- Broader evaluations after keeping the scored benchmark intact

## How Work Is Measured

A method is judged through the rating program `scripts/rate.sh` on games the evaluators supply, including hidden games generated at test time. Its ratings must be the deviation gains of a coarse correlated equilibrium it returns. Within that family the scored question is equilibrium selection: which CCE gives ratings that stay equal on cyclic games and invariant to clones, mixtures, offsets and extra players? The reproduced method already scores exactly 0 on every invariance metric, so measurable progress means matching it with a better method (faster, larger games, more players, more robust numerics) without losing any property.

## Out of Bounds
- Replacing the problem with ordinary pairwise ranking or a non-game-theoretic leaderboard fit
- Using the benchmark's exact numerical targets without recomputation
- Modifying the scored game definitions or metric meanings while still claiming direct improvement on this gym
- Rating programs that read or alter the evaluator, special-case recognizable games, or leave processes or files behind to affect scoring
