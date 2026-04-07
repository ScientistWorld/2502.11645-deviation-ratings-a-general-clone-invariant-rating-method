# Research Direction

## Research Problem

This paper introduces deviation ratings — a game-theoretic method for rating strategies in N-player general-sum normal-form games. The core challenge is: how do you rate strategies when interactions are strategic (adversarial, cooperative, or mixed-motive) and involve more than two players?

## Core Contribution

The paper's novelty is using coarse correlated equilibrium (CCE) deviation gains as the rating signal, and selecting the strictest CCE (minimizing the maximum deviation gain) to produce unique ratings. This achieves clone invariance for the first time in N-player general-sum games.

The scientist must work within this paradigm: equilibrium-based ratings derived from deviation gains.

## Approach Scope

The scientist may explore:
- Improving the LP solving (warm-starting, better solvers, constraint preprocessing)
- Handling numerical stability better (quantization, preconditioning)
- Extending to larger games through decomposition or approximation
- Alternative equilibrium selection criteria that preserve clone invariance
- Applications to new domains after preserving the scored experiments

## Out of Bounds
- Replacing CCE deviation gains with a fundamentally different rating approach (e.g., pure Elo, PageRank, or non-game-theoretic scoring). The paper's thesis is that game-theoretic equilibria enable clone invariance — sidestepping that defeats the purpose.
- Using the paper's exact numerical outputs without recomputation.
- Modifying the problem formulation (e.g., changing the game structure, payoff normalization) without justification.
