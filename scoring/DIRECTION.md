# Research Direction

## Research Problem

The benchmark studies how to rate strategies in multi-player, general-sum normal-form games when interactions are strategic rather than purely transitive. The core challenge is to produce ratings that remain meaningful when there are cycles, mixed motives, and redundant strategies.

## Scope

Scientists should work on principled game-theoretic rating methods that are appropriate for normal-form games and that respect the benchmark's invariance requirements. Work that merely fits a scalar ranking to the final tables, without modeling the strategic game structure, is out of scope.

## Approach Scope

The scientist may explore:
- Better optimization or numerical methods for computing ratings
- Alternative principled rating formulations for the same problem family
- Improved scalability to larger games while preserving the scored properties
- Broader evaluations or extra experiments after keeping the scored benchmark intact

## Out of Bounds
- Replacing the problem with ordinary pairwise ranking or a non-game-theoretic leaderboard fit
- Using the paper's exact numerical outputs without recomputation.
- Modifying the scored game definitions or metric meanings while still claiming direct improvement on this gym.
