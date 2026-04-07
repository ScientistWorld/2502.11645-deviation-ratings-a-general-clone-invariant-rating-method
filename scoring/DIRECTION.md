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

## Out of Bounds
- Replacing the problem with ordinary pairwise ranking or a non-game-theoretic leaderboard fit
- Using the benchmark's exact numerical targets without recomputation
- Modifying the scored game definitions or metric meanings while still claiming direct improvement on this gym
