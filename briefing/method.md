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
3. From the LP solution, identify which deviation gain constraints are active: those with a nonzero dual variable (Section 4.1). By complementary slackness they are tight at every optimal distribution
4. Freeze those constraints (add them to the active set) with their computed ratings. A constraint that is tight at the returned vertex but has a zero dual is not frozen yet; if it is truly pinned it is frozen in a later iteration at the same value
5. Repeat until all strategies are rated

The LP finds the **strictest CCE** — the equilibrium where no player can gain the most by deviating. Since ratings are derived from the objective value (not the solution parameters), the ratings are unique even though many equilibria may exist.

### Computational Approach

The paper reports using CVXPY with GLOP (OR-Tools' simplex solver) as the backend. This reproduction keeps the same sequential-LP algorithm but implements it with SciPy's `linprog` (HiGHS backend) instead of CVXPY/GLOP (`method/deviation_rating.py`). The benchmark calls it through the rating program `scripts/rate.sh` -> `method/rate.py`, which returns, for every game, the ratings and the final LP's distribution, under which every rating is exactly the corresponding deviation gain.

An earlier version of this implementation also froze every constraint that happened to be numerically tight at the vertex the solver returned. When the optimal face is not a single point, for example when one player's best action pins epsilon at 0, that freezes ratings that later iterations should lower. The result then depends on the solver's vertex choice and loses uniqueness and invariance: it failed the hidden invariance checks on every one of 11 sampled test suites. The current default follows the paper's nonzero-dual rule (`freeze_rule="dual"`). The old rule is kept only as a diagnostic (`freeze_rule="active"`). The algorithm still runs in polynomial time since it solves sequential LPs, each in polynomial time. The maximum number of outer iterations is $\sum_p |A_p|$ (number of constraints).

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
