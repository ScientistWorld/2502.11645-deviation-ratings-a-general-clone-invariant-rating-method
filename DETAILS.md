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

---

# Evaluation

How success is measured for a game-theoretic rating method.

## How a method is scored

A method is a **rating program**: `bash scripts/rate.sh GAMES_JSON RATINGS_JSON`. The evaluators write the games, run the program, and score what it returns. Methods never get the scored games ahead of time: the hidden test generates its games when it runs.

Input (written by the evaluator):

```json
{"games": [{"id": "<opaque id>", "payoffs": P}, ...]}
```

`P` has shape `[N][A_1]...[A_N]`: `P[p][a_1]...[a_N]` is player `p`'s payoff at the joint action `(a_1, ..., a_N)`. Games have 2 or 3 players and can include players with a single action.

Output (written by the method):

```json
{"results": {"<id>": {"ratings": [[r_0(0), r_0(1), ...], [r_1(0), ...], ...],
                      "equilibrium": [s_0, s_1, ...]}}}
```

`ratings[p][a]` is the rating of player `p`'s action `a`. `equilibrium` is the joint recommendation distribution the ratings come from, as a flat list of `A_1 * ... * A_N` probabilities in C (row-major) order.

### Validity gates

Every game's output must pass all of these:

- every rating and probability is a finite JSON number (no `NaN`, `Infinity`, strings, booleans or nulls), with exactly one rating per action of every player;
- the distribution is non-negative and sums to 1 (tolerance 1e-6);
- the distribution is a coarse correlated equilibrium: every deviation gain `sum_a s(a) [G_p(a'_p, a_-p) - G_p(a)]` is at most `1e-6 * scale`;
- the ratings **are** those deviation gains of the submitted distribution, within `1e-6 * scale`.

Here `scale = max(1, largest absolute payoff in the game)`. If any game fails a gate, every experiment containing that game is **scored as failed**: its lower-is-better metrics are set to `1e6` and `min_margin` to `-1e6`. If the rating program crashes, times out (30 minutes) or writes malformed output, all five experiments fail.

Every scored number is recomputed from the payoffs and the submitted distribution. Numbers the method reports are only compared against these recomputed values, never used directly. Rating differences of at most `1e-6 * scale` count as 0, and metrics are rounded to 6 decimals.

### Evaluators

| Command | Games | Output |
|---|---|---|
| `bash scripts/evaluate.sh` | the five documented public games below | `scoring/scores.json` |
| `bash scripts/evaluate_train.sh` | the same five public games | `scoring/scores_train.json` |
| `bash scripts/evaluate_test.sh` (hidden, no arguments) | about 190 games generated at test time from the families below | `scoring/scores_test.json` |

The evaluators run with `python3 -I`, ignoring `PYTHONPATH`, user site-packages and the working directory. They do not read `checkpoints/`, `data/`, `baseline/` or `scoring/reference.json`. The rating program runs in a fresh temporary directory, receives the games anonymised and shuffled, and every process it started is killed before scoring begins. Baselines are computed by the evaluator itself.

## Experiments

Each metric is a maximum over the experiment's games (dominance violations are summed). Lower is better except `min_margin`.

1. **`biased_shapley_augmented`: no artificial order in cyclic games.**
   - Public game: the paper's Table 2 biased Shapley game augmented with its Nash mixture `N`.
   - Hidden games: games whose deviation ratings are provably all equal. These are the biased Shapley game with and without `N`, symmetric populations of random mixtures of R/P/S, scaled, offset, cloned and relabeled variants, and variants with an extra bystander player (see below). They also include zero-sum rock-paper-scissors, randomly weighted RPS, and RPS-lizard-Spock.
   - `dev_gap`: rating spread of the first cyclic player's actions.
   - `all_player_dev_gap`: spread across both cyclic players.
   - `player_symmetry_gap`: largest same-strategy mismatch between the two players.
   - `CCE_gap`: total CCE regret of the submitted distribution.

2. **`clone_invariance`: duplicating a strategy changes nothing.**
   - Public game: rock-paper-scissors with player 1's rock cloned.
   - Hidden games: random 2- and 3-player general-sum, zero-sum and common-interest games, and games with a bystander. Each gets a clone of one action inserted at a random position, and every player's actions are relabeled.
   - `max_diff`: change in the ratings of the other players' strategies, the ones that face the clone.
   - `all_players_max_diff`: change over all original actions of all players.
   - `clone_source_gap`: clone's rating versus its source.

3. **`mixture_invariance`: adding a mixed strategy changes nothing, and the mixture gets the mixed rating.**
   - The evaluator fixes the mixture weights: `[0.3, 0.7]` on the public general-sum game, random weights over random subsets of actions on the hidden games.
   - `original_max_diff`: change in any original rating, all players.
   - `mixture_error`: the mixture's rating minus the same mixture of the original ratings.
   - `max_CCE_gap`: worst CCE regret of the base and augmented games.

4. **`offset_invariance`: adding `b_p(a_-p)` to payoffs changes nothing.**
   - Public game: offsets `[[10, -4], [7, -3]]` on the general-sum game.
   - Hidden games: random offsets in `[-5, 5]` for every player and opponent profile, plus relabeling.
   - `max_diff`: absolute (uncentered) change of any rating.
   - `max_CCE_gap`: worst CCE regret of the base and offset games.

5. **`dominance_preserving`: a strictly dominant strategy is rated higher.**
   - The evaluator finds every strictly dominated `(player, better, worse)` pair in the game itself. Each game contains at least one pair with a constant payoff gap.
   - Public game: the 2x2 game where action 0 dominates for both players.
   - `dominance_violations`: pairs whose rating advantage is not positive.
   - `min_margin`: smallest ratio of rating advantage to guaranteed payoff advantage. On a constant-gap pair this ratio is exactly 1 for any rating that is the deviation gain of some distribution, so the value cannot exceed 1. It shows whether a method stays in units of payoff, not how far it separates actions.
   - `CCE_gap`: total CCE regret of the submitted distribution.

### Bystander players

Some hidden games add a player whose payoff depends only on its own action. Such a player does not change the other players' deviation ratings. Its best action has deviation gain 0 under every CCE, though, so the strictest equilibrium of the remaining players is not visible to a single "minimize the largest deviation gain" LP. A method must keep selecting among the remaining equilibria to rate them consistently.

## Baselines

All baselines are computed by the evaluator on the same games, never by the submission:

- `uniform_payoff` (every experiment): mean payoff over all opponent profiles. Its CCE gap is that of the uniform joint distribution.
- `zero_rating` and `negative_uniform_payoff` (dominance only): constant zero ratings and negated uniform ratings.

On the public games, the uniform baseline has a Shapley spread of 1.25, clone difference 0.25, mixture drift 0.133333 and offset change 3.0, and violates the CCE condition. The deviation rating reproduction scores 0 on all of these. Baseline rows are reference points and are not subject to the method gates.

## What the test does and does not establish

The test checks the properties the paper proves (Table 1 and Section 5.1) on games no submission can see beforehand. It does not check which algorithm produced the distribution. Any rating that is the deviation gain of a CCE and is exactly equal on the cyclic games and invariant on these families scores like the reference.

## Packaged scope

The paper also reports LiveBench and policy-improvement studies. They are not part of the scored benchmark.

---

# Reproduction Log

### Iteration 1: MiniMax-M2.7
- **Milestone**: `method_runs` | **Status**: done
- **Working time**: 2.3h | **GPU**: 0.0h
- **Jobs**: 1 total (1 completed, 0 failed)

<details>
<summary>Progress Log</summary>

### [2026-04-05] - method_runs
- Algorithm runs end-to-end with scipy.optimize.linprog
- Livebench works (top4_overlap=4/4) — 3-player game converges correctly
- Population study works (dev spread=0) — symmetric games solve correctly
- Previous issue: biased Shapley game (3x3) didn't converge to CCE_gap=0 with ECOS
- Fix: replaced CVXPY/ECOS with scipy.optimize.linprog for more reliable LP solving
- The strictest CCE of the biased Shapley game should be a pure NE → CCE_gap=0

### [2026-04-04] - none
- Initial workspace setup, read the paper thoroughly

</details>

### Iteration 2: glm-5.1
- **Milestone**: `core_claim` | **Status**: done
- **Working time**: 32m | **GPU**: 0.0h
- **Jobs**: 1 total (1 completed, 0 failed)

<details>
<summary>Progress Log</summary>

### 2026-04-07 - method_runs
- Fixed missing imports in deviation_rating.py (Any) and evaluate.py (Dict)
- Verified algorithm works locally: LLM rating passes (top4_overlap=4, CCE_gap=0.0)
- Deviation rating algorithm (Algorithm 1) correctly implements sequential LP via scipy.optimize.linprog
- CCE_gap ≈ 0 for all experiments - algorithm finds valid Coarse Correlated Equilibria
- **Container build blocked by Docker Hub rate limit** - tried Docker Hub, ghcr.io, quay.io, Singularity Hub (all rate-limited or require auth)

</details>

### Iteration 3: glm-5.1
- **Milestone**: `core_claim` | **Status**: done
- **Working time**: 56m | **GPU**: 0.0h
- **Jobs**: 1 total (1 completed, 0 failed)

<details>
<summary>Progress Log</summary>

### [2026-04-07 00:00] - none
- Read the paper and inspected the existing workspace implementation
- Identified the paper's minimum reproducible claims as the augmented biased Shapley example and clone invariance

### [2026-04-07 00:00] - method_runs
- Implemented and corrected the sequential LP deviation-rating pipeline
- Added reproducible method, baseline, evaluation, and end-to-end shell scripts
- Verified the algorithm executes end-to-end without errors

### [2026-04-07 00:00] - core_claim
- Reproduced the paper's augmented biased Shapley result with `dev_gap = 0.0` and `CCE_gap = 0.0`
- Reproduced exact clone invariance on cloned RPS with `max_diff = 0.0`
- Validated the environment with `bash scripts/reproduce.sh` and `python validate.py --compare`

</details>

### Iteration 4: glm-5.1 (verifier)
- **Milestone**: `core_claim` | **Status**: done
- **Working time**: 1m | **GPU**: 0.0h
- **Jobs**: 1 total (1 completed, 0 failed)

<details>
<summary>Progress Log</summary>

### [2026-04-07 00:00] - none
- Read the paper and inspected the existing workspace implementation
- Identified the paper's minimum reproducible claims as the augmented biased Shapley example and clone invariance

### [2026-04-07 00:00] - method_runs
- Implemented and corrected the sequential LP deviation-rating pipeline
- Added reproducible method, baseline, evaluation, and end-to-end shell scripts
- Verified the algorithm executes end-to-end without errors

### [2026-04-07 00:00] - core_claim
- Reproduced the paper's augmented biased Shapley result with `dev_gap = 0.0` and `CCE_gap = 0.0`
- Reproduced exact clone invariance on cloned RPS with `max_diff = 0.0`
- Validated the environment with `bash scripts/reproduce.sh` and `python validate.py --compare`

### [2026-04-07 22:22] - core_claim
- Installed the declared runtime dependencies into `/home/user/pkgs` on the login node for a real local verification pass
- Re-ran `bash scripts/reproduce.sh` successfully and confirmed `python3 validate.py --compare` passes
- Prepared a CPU-only submission to validate the packaged environment through `scripts/run.sh`

### [2026-04-07 22:35] - core_claim
- Verified the workspace as a gym package rather than a reproduction attempt
- Fixed method leakage in the method-agnostic and method-safe scoring/briefing documents
- Confirmed the existing `core_claim` milestone remains accurate after documentation cleanup

### [2026-04-07 22:50] - core_claim
- Completed final wrap-up of milestone, progress, and scoring guidance documents
- Confirmed `python3 validate.py` passes with the final scoring contract
- Finalized the repository as a `core_claim` research gym and closed the paper with `action: done`

</details>

### Iteration 5: glm-5.1 (verifier)
- **Milestone**: `secondary_claims` | **Status**: done
- **Working time**: 23m | **GPU**: 0.0h
- **Jobs**: 1 total (1 completed, 0 failed)

<details>
<summary>Progress Log</summary>

### [2026-04-07 00:00] - none
- Read the paper and inspected the existing workspace implementation
- Identified the paper's minimum reproducible claims as the augmented biased Shapley example and clone invariance

### [2026-04-07 00:00] - method_runs
- Implemented and corrected the sequential LP deviation-rating pipeline
- Added reproducible method, baseline, evaluation, and end-to-end shell scripts
- Verified the algorithm executes end-to-end without errors

### [2026-04-07 00:00] - core_claim
- Reproduced the paper's augmented biased Shapley result with `dev_gap = 0.0` and `CCE_gap = 0.0`
- Reproduced exact clone invariance on cloned RPS with `max_diff = 0.0`
- Validated the environment with `bash scripts/reproduce.sh` and `python validate.py --compare`

### [2026-04-07 22:22] - core_claim
- Installed the declared runtime dependencies into `/home/user/pkgs` on the login node for a real local verification pass
- Re-ran `bash scripts/reproduce.sh` successfully and confirmed `python3 validate.py --compare` passes
- Prepared a CPU-only submission to validate the packaged environment through `scripts/run.sh`

### [2026-04-07 22:35] - core_claim
- Verified the workspace as a gym package rather than a reproduction attempt
- Fixed method leakage in the method-agnostic and method-safe scoring/briefing documents
- Confirmed the existing `core_claim` milestone remains accurate after documentation cleanup

### [2026-04-07 22:50] - core_claim
- Completed final wrap-up of milestone, progress, and scoring guidance documents
- Confirmed `python3 validate.py` passes with the final scoring contract
- Finalized the repository as a `core_claim` research gym and closed the paper with `action: done`

### [2026-04-07 23:10] - secondary_claims
- Extended the packaged benchmark from two to five scored paper properties: clone invariance, mixture invariance, offset invariance, dominance preservation, and the augmented biased Shapley equality result
- Fixed the sequential LP active-set update to freeze all numerically active max-deviation constraints at each optimum, not only constraints with nonzero dual marginals
- Re-ran `bash scripts/reproduce.sh` and `python3 validate.py --compare` successfully with the new five-experiment scoring contract
- Prepared a CPU-only scheduler validation run for the packaged environment

### [2026-04-07 23:30] - secondary_claims
- Verified that `eval/` and `data/` are cleanly separated from `method/`
- Confirmed the scoring contract still passes with `python3 validate.py --compare`
- Fixed `scoring/EXPERIMENTS.md` so it matches the five scored experiments exactly
- Removed a latent undeclared LiveBench scoring path from `eval/evaluate.py`
- Recorded the final verification judgment in `VERIFICATION.md`

</details>

### Iteration 6: gpt-5.4 (packager)
- **Milestone**: `secondary_claims` | **Status**: done
- **Working time**: 2m | **GPU**: 0.0h
- **Jobs**: 1 total (1 completed, 0 failed)

<details>
<summary>Progress Log</summary>

### [2026-04-07 00:00] - none
- Read the paper and inspected the existing workspace implementation
- Identified the paper's minimum reproducible claims as the augmented biased Shapley example and clone invariance

### [2026-04-07 00:00] - method_runs
- Implemented and corrected the sequential LP deviation-rating pipeline
- Added reproducible method, baseline, evaluation, and end-to-end shell scripts
- Verified the algorithm executes end-to-end without errors

### [2026-04-07 00:00] - core_claim
- Reproduced the paper's augmented biased Shapley result with `dev_gap = 0.0` and `CCE_gap = 0.0`
- Reproduced exact clone invariance on cloned RPS with `max_diff = 0.0`
- Validated the environment with `bash scripts/reproduce.sh` and `python validate.py --compare`

### [2026-04-07 22:22] - core_claim
- Installed the declared runtime dependencies into `/home/user/pkgs` on the login node for a real local verification pass
- Re-ran `bash scripts/reproduce.sh` successfully and confirmed `python3 validate.py --compare` passes
- Prepared a CPU-only submission to validate the packaged environment through `scripts/run.sh`

### [2026-04-07 22:35] - core_claim
- Verified the workspace as a gym package rather than a reproduction attempt
- Fixed method leakage in the method-agnostic and method-safe scoring/briefing documents
- Confirmed the existing `core_claim` milestone remains accurate after documentation cleanup

### [2026-04-07 22:50] - core_claim
- Completed final wrap-up of milestone, progress, and scoring guidance documents
- Confirmed `python3 validate.py` passes with the final scoring contract
- Finalized the repository as a `core_claim` research gym and closed the paper with `action: done`

### [2026-04-07 23:10] - secondary_claims
- Extended the packaged benchmark from two to five scored paper properties: clone invariance, mixture invariance, offset invariance, dominance preservation, and the augmented biased Shapley equality result
- Fixed the sequential LP active-set update to freeze all numerically active max-deviation constraints at each optimum, not only constraints with nonzero dual marginals
- Re-ran `bash scripts/reproduce.sh` and `python3 validate.py --compare` successfully with the new five-experiment scoring contract
- Prepared a CPU-only scheduler validation run for the packaged environment

### [2026-04-07 23:30] - secondary_claims
- Verified that `eval/` and `data/` are cleanly separated from `method/`
- Confirmed the scoring contract still passes with `python3 validate.py --compare`
- Fixed `scoring/EXPERIMENTS.md` so it matches the five scored experiments exactly
- Removed a latent undeclared LiveBench scoring path from `eval/evaluate.py`
- Recorded the final verification judgment in `VERIFICATION.md`

</details>

### Iteration 7: gpt-5.4 (designer)
- **Milestone**: `secondary_claims` | **Status**: done
- **Working time**: 8m | **GPU**: 0.0h
- **Jobs**: 1 total (1 completed, 0 failed)

<details>
<summary>Progress Log</summary>

### [2026-04-07 00:00] - none
- Read the paper and inspected the existing workspace implementation
- Identified the paper's minimum reproducible claims as the augmented biased Shapley example and clone invariance

### [2026-04-07 00:00] - method_runs
- Implemented and corrected the sequential LP deviation-rating pipeline
- Added reproducible method, baseline, evaluation, and end-to-end shell scripts
- Verified the algorithm executes end-to-end without errors

### [2026-04-07 00:00] - core_claim
- Reproduced the paper's augmented biased Shapley result with `dev_gap = 0.0` and `CCE_gap = 0.0`
- Reproduced exact clone invariance on cloned RPS with `max_diff = 0.0`
- Validated the environment with `bash scripts/reproduce.sh` and `python validate.py --compare`

### [2026-04-07 22:22] - core_claim
- Installed the declared runtime dependencies into `/home/user/pkgs` on the login node for a real local verification pass
- Re-ran `bash scripts/reproduce.sh` successfully and confirmed `python3 validate.py --compare` passes
- Prepared a CPU-only submission to validate the packaged environment through `scripts/run.sh`

### [2026-04-07 22:35] - core_claim
- Verified the workspace as a gym package rather than a reproduction attempt
- Fixed method leakage in the method-agnostic and method-safe scoring/briefing documents
- Confirmed the existing `core_claim` milestone remains accurate after documentation cleanup

### [2026-04-07 22:50] - core_claim
- Completed final wrap-up of milestone, progress, and scoring guidance documents
- Confirmed `python3 validate.py` passes with the final scoring contract
- Finalized the repository as a `core_claim` research gym and closed the paper with `action: done`

### [2026-04-07 23:10] - secondary_claims
- Extended the packaged benchmark from two to five scored paper properties: clone invariance, mixture invariance, offset invariance, dominance preservation, and the augmented biased Shapley equality result
- Fixed the sequential LP active-set update to freeze all numerically active max-deviation constraints at each optimum, not only constraints with nonzero dual marginals
- Re-ran `bash scripts/reproduce.sh` and `python3 validate.py --compare` successfully with the new five-experiment scoring contract
- Prepared a CPU-only scheduler validation run for the packaged environment

### [2026-04-07 23:30] - secondary_claims
- Verified that `eval/` and `data/` are cleanly separated from `method/`
- Confirmed the scoring contract still passes with `python3 validate.py --compare`
- Fixed `scoring/EXPERIMENTS.md` so it matches the five scored experiments exactly
- Removed a latent undeclared LiveBench scoring path from `eval/evaluate.py`
- Recorded the final verification judgment in `VERIFICATION.md`

</details>

### Iteration 7: MiniMax-M2.7 (designer_stage_1)
- **Milestone**: `secondary_claims` | **Status**: done
- **Working time**: 4m | **GPU**: 0.0h
- **Jobs**: 1 total (1 completed, 0 failed)

<details>
<summary>Progress Log</summary>

### [2026-04-07 00:00] - none
- Read the paper and inspected the existing workspace implementation
- Identified the paper's minimum reproducible claims as the augmented biased Shapley example and clone invariance

### [2026-04-07 00:00] - method_runs
- Implemented and corrected the sequential LP deviation-rating pipeline
- Added reproducible method, baseline, evaluation, and end-to-end shell scripts
- Verified the algorithm executes end-to-end without errors

### [2026-04-07 00:00] - core_claim
- Reproduced the paper's augmented biased Shapley result with `dev_gap = 0.0` and `CCE_gap = 0.0`
- Reproduced exact clone invariance on cloned RPS with `max_diff = 0.0`
- Validated the environment with `bash scripts/reproduce.sh` and `python validate.py --compare`

### [2026-04-07 22:22] - core_claim
- Installed the declared runtime dependencies into `/home/user/pkgs` on the login node for a real local verification pass
- Re-ran `bash scripts/reproduce.sh` successfully and confirmed `python3 validate.py --compare` passes
- Prepared a CPU-only submission to validate the packaged environment through `scripts/run.sh`

### [2026-04-07 22:35] - core_claim
- Verified the workspace as a gym package rather than a reproduction attempt
- Fixed method leakage in the method-agnostic and method-safe scoring/briefing documents
- Confirmed the existing `core_claim` milestone remains accurate after documentation cleanup

### [2026-04-07 22:50] - core_claim
- Completed final wrap-up of milestone, progress, and scoring guidance documents
- Confirmed `python3 validate.py` passes with the final scoring contract
- Finalized the repository as a `core_claim` research gym and closed the paper with `action: done`

### [2026-04-07 23:10] - secondary_claims
- Extended the packaged benchmark from two to five scored paper properties: clone invariance, mixture invariance, offset invariance, dominance preservation, and the augmented biased Shapley equality result
- Fixed the sequential LP active-set update to freeze all numerically active max-deviation constraints at each optimum, not only constraints with nonzero dual marginals
- Re-ran `bash scripts/reproduce.sh` and `python3 validate.py --compare` successfully with the new five-experiment scoring contract
- Prepared a CPU-only scheduler validation run for the packaged environment

### [2026-04-07 23:30] - secondary_claims
- Verified that `eval/` and `data/` are cleanly separated from `method/`
- Confirmed the scoring contract still passes with `python3 validate.py --compare`
- Fixed `scoring/EXPERIMENTS.md` so it matches the five scored experiments exactly
- Removed a latent undeclared LiveBench scoring path from `eval/evaluate.py`
- Recorded the final verification judgment in `VERIFICATION.md`

</details>

### Iteration 8: MiniMax-M2.7 (designer_stage_2)
- **Milestone**: `secondary_claims` | **Status**: done
- **Working time**: 3m | **GPU**: 0.0h
- **Jobs**: 1 total (1 completed, 0 failed)

<details>
<summary>Progress Log</summary>

### [2026-04-07 00:00] - none
- Read the paper and inspected the existing workspace implementation
- Identified the paper's minimum reproducible claims as the augmented biased Shapley example and clone invariance

### [2026-04-07 00:00] - method_runs
- Implemented and corrected the sequential LP deviation-rating pipeline
- Added reproducible method, baseline, evaluation, and end-to-end shell scripts
- Verified the algorithm executes end-to-end without errors

### [2026-04-07 00:00] - core_claim
- Reproduced the paper's augmented biased Shapley result with `dev_gap = 0.0` and `CCE_gap = 0.0`
- Reproduced exact clone invariance on cloned RPS with `max_diff = 0.0`
- Validated the environment with `bash scripts/reproduce.sh` and `python validate.py --compare`

### [2026-04-07 22:22] - core_claim
- Installed the declared runtime dependencies into `/home/user/pkgs` on the login node for a real local verification pass
- Re-ran `bash scripts/reproduce.sh` successfully and confirmed `python3 validate.py --compare` passes
- Prepared a CPU-only submission to validate the packaged environment through `scripts/run.sh`

### [2026-04-07 22:35] - core_claim
- Verified the workspace as a gym package rather than a reproduction attempt
- Fixed method leakage in the method-agnostic and method-safe scoring/briefing documents
- Confirmed the existing `core_claim` milestone remains accurate after documentation cleanup

### [2026-04-07 22:50] - core_claim
- Completed final wrap-up of milestone, progress, and scoring guidance documents
- Confirmed `python3 validate.py` passes with the final scoring contract
- Finalized the repository as a `core_claim` research gym and closed the paper with `action: done`

### [2026-04-07 23:10] - secondary_claims
- Extended the packaged benchmark from two to five scored paper properties: clone invariance, mixture invariance, offset invariance, dominance preservation, and the augmented biased Shapley equality result
- Fixed the sequential LP active-set update to freeze all numerically active max-deviation constraints at each optimum, not only constraints with nonzero dual marginals
- Re-ran `bash scripts/reproduce.sh` and `python3 validate.py --compare` successfully with the new five-experiment scoring contract
- Prepared a CPU-only scheduler validation run for the packaged environment

### [2026-04-07 23:30] - secondary_claims
- Verified that `eval/` and `data/` are cleanly separated from `method/`
- Confirmed the scoring contract still passes with `python3 validate.py --compare`
- Fixed `scoring/EXPERIMENTS.md` so it matches the five scored experiments exactly
- Removed a latent undeclared LiveBench scoring path from `eval/evaluate.py`
- Recorded the final verification judgment in `VERIFICATION.md`

</details>

### Iteration 9: gpt-5.4 (designer_stage_3)
- **Milestone**: `secondary_claims` | **Status**: done
- **Working time**: 8m | **GPU**: 0.0h
- **Jobs**: 2 total (2 completed, 0 failed)

<details>
<summary>Progress Log</summary>

### [2026-04-07 00:00] - none
- Read the paper and inspected the existing workspace implementation
- Identified the paper's minimum reproducible claims as the augmented biased Shapley example and clone invariance

### [2026-04-07 00:00] - method_runs
- Implemented and corrected the sequential LP deviation-rating pipeline
- Added reproducible method, baseline, evaluation, and end-to-end shell scripts
- Verified the algorithm executes end-to-end without errors

### [2026-04-07 00:00] - core_claim
- Reproduced the paper's augmented biased Shapley result with `dev_gap = 0.0` and `CCE_gap = 0.0`
- Reproduced exact clone invariance on cloned RPS with `max_diff = 0.0`
- Validated the environment with `bash scripts/reproduce.sh` and `python validate.py --compare`

### [2026-04-07 22:22] - core_claim
- Installed the declared runtime dependencies into `/home/user/pkgs` on the login node for a real local verification pass
- Re-ran `bash scripts/reproduce.sh` successfully and confirmed `python3 validate.py --compare` passes
- Prepared a CPU-only submission to validate the packaged environment through `scripts/run.sh`

### [2026-04-07 22:35] - core_claim
- Verified the workspace as a gym package rather than a reproduction attempt
- Fixed method leakage in the method-agnostic and method-safe scoring/briefing documents
- Confirmed the existing `core_claim` milestone remains accurate after documentation cleanup

### [2026-04-07 22:50] - core_claim
- Completed final wrap-up of milestone, progress, and scoring guidance documents
- Confirmed `python3 validate.py` passes with the final scoring contract
- Finalized the repository as a `core_claim` research gym and closed the paper with `action: done`

### [2026-04-07 23:10] - secondary_claims
- Extended the packaged benchmark from two to five scored paper properties: clone invariance, mixture invariance, offset invariance, dominance preservation, and the augmented biased Shapley equality result
- Fixed the sequential LP active-set update to freeze all numerically active max-deviation constraints at each optimum, not only constraints with nonzero dual marginals
- Re-ran `bash scripts/reproduce.sh` and `python3 validate.py --compare` successfully with the new five-experiment scoring contract
- Prepared a CPU-only scheduler validation run for the packaged environment

### [2026-04-07 23:30] - secondary_claims
- Verified that `eval/` and `data/` are cleanly separated from `method/`
- Confirmed the scoring contract still passes with `python3 validate.py --compare`
- Fixed `scoring/EXPERIMENTS.md` so it matches the five scored experiments exactly
- Removed a latent undeclared LiveBench scoring path from `eval/evaluate.py`
- Recorded the final verification judgment in `VERIFICATION.md`

</details>

### Iteration 4: MiniMax-M2.7 (designer_stage_1)
- **Milestone**: `secondary_claims` | **Status**: done
- **Working time**: 3m | **GPU**: 0.0h
- **Jobs**: 2 total (2 completed, 0 failed)

<details>
<summary>Progress Log</summary>

### [2026-04-07 00:00] - none
- Read the paper and inspected the existing workspace implementation
- Identified the paper's minimum reproducible claims as the augmented biased Shapley example and clone invariance

### [2026-04-07 00:00] - method_runs
- Implemented and corrected the sequential LP deviation-rating pipeline
- Added reproducible method, baseline, evaluation, and end-to-end shell scripts
- Verified the algorithm executes end-to-end without errors

### [2026-04-07 00:00] - core_claim
- Reproduced the paper's augmented biased Shapley result with `dev_gap = 0.0` and `CCE_gap = 0.0`
- Reproduced exact clone invariance on cloned RPS with `max_diff = 0.0`
- Validated the environment with `bash scripts/reproduce.sh` and `python validate.py --compare`

### [2026-04-07 22:22] - core_claim
- Installed the declared runtime dependencies into `/home/user/pkgs` on the login node for a real local verification pass
- Re-ran `bash scripts/reproduce.sh` successfully and confirmed `python3 validate.py --compare` passes
- Prepared a CPU-only submission to validate the packaged environment through `scripts/run.sh`

### [2026-04-07 22:35] - core_claim
- Verified the workspace as a gym package rather than a reproduction attempt
- Fixed method leakage in the method-agnostic and method-safe scoring/briefing documents
- Confirmed the existing `core_claim` milestone remains accurate after documentation cleanup

### [2026-04-07 22:50] - core_claim
- Completed final wrap-up of milestone, progress, and scoring guidance documents
- Confirmed `python3 validate.py` passes with the final scoring contract
- Finalized the repository as a `core_claim` research gym and closed the paper with `action: done`

### [2026-04-07 23:10] - secondary_claims
- Extended the packaged benchmark from two to five scored paper properties: clone invariance, mixture invariance, offset invariance, dominance preservation, and the augmented biased Shapley equality result
- Fixed the sequential LP active-set update to freeze all numerically active max-deviation constraints at each optimum, not only constraints with nonzero dual marginals
- Re-ran `bash scripts/reproduce.sh` and `python3 validate.py --compare` successfully with the new five-experiment scoring contract
- Prepared a CPU-only scheduler validation run for the packaged environment

### [2026-04-07 23:30] - secondary_claims
- Verified that `eval/` and `data/` are cleanly separated from `method/`
- Confirmed the scoring contract still passes with `python3 validate.py --compare`
- Fixed `scoring/EXPERIMENTS.md` so it matches the five scored experiments exactly
- Removed a latent undeclared LiveBench scoring path from `eval/evaluate.py`
- Recorded the final verification judgment in `VERIFICATION.md`

</details>

### Iteration 5: MiniMax-M2.7 (designer_stage_2)
- **Milestone**: `secondary_claims` | **Status**: done
- **Working time**: 2m | **GPU**: 0.0h
- **Jobs**: 2 total (2 completed, 0 failed)

<details>
<summary>Progress Log</summary>

### [2026-04-07 00:00] - none
- Read the paper and inspected the existing workspace implementation
- Identified the paper's minimum reproducible claims as the augmented biased Shapley example and clone invariance

### [2026-04-07 00:00] - method_runs
- Implemented and corrected the sequential LP deviation-rating pipeline
- Added reproducible method, baseline, evaluation, and end-to-end shell scripts
- Verified the algorithm executes end-to-end without errors

### [2026-04-07 00:00] - core_claim
- Reproduced the paper's augmented biased Shapley result with `dev_gap = 0.0` and `CCE_gap = 0.0`
- Reproduced exact clone invariance on cloned RPS with `max_diff = 0.0`
- Validated the environment with `bash scripts/reproduce.sh` and `python validate.py --compare`

### [2026-04-07 22:22] - core_claim
- Installed the declared runtime dependencies into `/home/user/pkgs` on the login node for a real local verification pass
- Re-ran `bash scripts/reproduce.sh` successfully and confirmed `python3 validate.py --compare` passes
- Prepared a CPU-only submission to validate the packaged environment through `scripts/run.sh`

### [2026-04-07 22:35] - core_claim
- Verified the workspace as a gym package rather than a reproduction attempt
- Fixed method leakage in the method-agnostic and method-safe scoring/briefing documents
- Confirmed the existing `core_claim` milestone remains accurate after documentation cleanup

### [2026-04-07 22:50] - core_claim
- Completed final wrap-up of milestone, progress, and scoring guidance documents
- Confirmed `python3 validate.py` passes with the final scoring contract
- Finalized the repository as a `core_claim` research gym and closed the paper with `action: done`

### [2026-04-07 23:10] - secondary_claims
- Extended the packaged benchmark from two to five scored paper properties: clone invariance, mixture invariance, offset invariance, dominance preservation, and the augmented biased Shapley equality result
- Fixed the sequential LP active-set update to freeze all numerically active max-deviation constraints at each optimum, not only constraints with nonzero dual marginals
- Re-ran `bash scripts/reproduce.sh` and `python3 validate.py --compare` successfully with the new five-experiment scoring contract
- Prepared a CPU-only scheduler validation run for the packaged environment

### [2026-04-07 23:30] - secondary_claims
- Verified that `eval/` and `data/` are cleanly separated from `method/`
- Confirmed the scoring contract still passes with `python3 validate.py --compare`
- Fixed `scoring/EXPERIMENTS.md` so it matches the five scored experiments exactly
- Removed a latent undeclared LiveBench scoring path from `eval/evaluate.py`
- Recorded the final verification judgment in `VERIFICATION.md`

</details>

### Iteration 6: gpt-5.4 (designer_stage_3)
- **Milestone**: `secondary_claims` | **Status**: done
- **Working time**: 14m | **GPU**: 0.0h
- **Jobs**: 5 total (5 completed, 0 failed)

<details>
<summary>Progress Log</summary>

### [2026-04-07 00:00] - none
- Read the paper and inspected the existing workspace implementation
- Identified the paper's minimum reproducible claims as the augmented biased Shapley example and clone invariance

### [2026-04-07 00:00] - method_runs
- Implemented and corrected the sequential LP deviation-rating pipeline
- Added reproducible method, baseline, evaluation, and end-to-end shell scripts
- Verified the algorithm executes end-to-end without errors

### [2026-04-07 00:00] - core_claim
- Reproduced the paper's augmented biased Shapley result with `dev_gap = 0.0` and `CCE_gap = 0.0`
- Reproduced exact clone invariance on cloned RPS with `max_diff = 0.0`
- Validated the environment with `bash scripts/reproduce.sh` and `python validate.py --compare`

### [2026-04-07 22:22] - core_claim
- Installed the declared runtime dependencies into `/home/user/pkgs` on the login node for a real local verification pass
- Re-ran `bash scripts/reproduce.sh` successfully and confirmed `python3 validate.py --compare` passes
- Prepared a CPU-only submission to validate the packaged environment through `scripts/run.sh`

### [2026-04-07 22:35] - core_claim
- Verified the workspace as a gym package rather than a reproduction attempt
- Fixed method leakage in the method-agnostic and method-safe scoring/briefing documents
- Confirmed the existing `core_claim` milestone remains accurate after documentation cleanup

### [2026-04-07 22:50] - core_claim
- Completed final wrap-up of milestone, progress, and scoring guidance documents
- Confirmed `python3 validate.py` passes with the final scoring contract
- Finalized the repository as a `core_claim` research gym and closed the paper with `action: done`

### [2026-04-07 23:10] - secondary_claims
- Extended the packaged benchmark from two to five scored paper properties: clone invariance, mixture invariance, offset invariance, dominance preservation, and the augmented biased Shapley equality result
- Fixed the sequential LP active-set update to freeze all numerically active max-deviation constraints at each optimum, not only constraints with nonzero dual marginals
- Re-ran `bash scripts/reproduce.sh` and `python3 validate.py --compare` successfully with the new five-experiment scoring contract
- Prepared a CPU-only scheduler validation run for the packaged environment

### [2026-04-07 23:30] - secondary_claims
- Verified that `eval/` and `data/` are cleanly separated from `method/`
- Confirmed the scoring contract still passes with `python3 validate.py --compare`
- Fixed `scoring/EXPERIMENTS.md` so it matches the five scored experiments exactly
- Removed a latent undeclared LiveBench scoring path from `eval/evaluate.py`
- Recorded the final verification judgment in `VERIFICATION.md`

</details>

### Iteration 7: gpt-5.4 (packager)
- **Milestone**: `secondary_claims` | **Status**: done
- **Working time**: 3m | **GPU**: 0.0h
- **Jobs**: 5 total (5 completed, 0 failed)

<details>
<summary>Progress Log</summary>

### [2026-04-07 00:00] - none
- Read the paper and inspected the existing workspace implementation
- Identified the paper's minimum reproducible claims as the augmented biased Shapley example and clone invariance

### [2026-04-07 00:00] - method_runs
- Implemented and corrected the sequential LP deviation-rating pipeline
- Added reproducible method, baseline, evaluation, and end-to-end shell scripts
- Verified the algorithm executes end-to-end without errors

### [2026-04-07 00:00] - core_claim
- Reproduced the paper's augmented biased Shapley result with `dev_gap = 0.0` and `CCE_gap = 0.0`
- Reproduced exact clone invariance on cloned RPS with `max_diff = 0.0`
- Validated the environment with `bash scripts/reproduce.sh` and `python validate.py --compare`

### [2026-04-07 22:22] - core_claim
- Installed the declared runtime dependencies into `/home/user/pkgs` on the login node for a real local verification pass
- Re-ran `bash scripts/reproduce.sh` successfully and confirmed `python3 validate.py --compare` passes
- Prepared a CPU-only submission to validate the packaged environment through `scripts/run.sh`

### [2026-04-07 22:35] - core_claim
- Verified the workspace as a gym package rather than a reproduction attempt
- Fixed method leakage in the method-agnostic and method-safe scoring/briefing documents
- Confirmed the existing `core_claim` milestone remains accurate after documentation cleanup

### [2026-04-07 22:50] - core_claim
- Completed final wrap-up of milestone, progress, and scoring guidance documents
- Confirmed `python3 validate.py` passes with the final scoring contract
- Finalized the repository as a `core_claim` research gym and closed the paper with `action: done`

### [2026-04-07 23:10] - secondary_claims
- Extended the packaged benchmark from two to five scored paper properties: clone invariance, mixture invariance, offset invariance, dominance preservation, and the augmented biased Shapley equality result
- Fixed the sequential LP active-set update to freeze all numerically active max-deviation constraints at each optimum, not only constraints with nonzero dual marginals
- Re-ran `bash scripts/reproduce.sh` and `python3 validate.py --compare` successfully with the new five-experiment scoring contract
- Prepared a CPU-only scheduler validation run for the packaged environment

### [2026-04-07 23:30] - secondary_claims
- Verified that `eval/` and `data/` are cleanly separated from `method/`
- Confirmed the scoring contract still passes with `python3 validate.py --compare`
- Fixed `scoring/EXPERIMENTS.md` so it matches the five scored experiments exactly
- Removed a latent undeclared LiveBench scoring path from `eval/evaluate.py`
- Recorded the final verification judgment in `VERIFICATION.md`

</details>

### Iteration 8: gpt-5.4 (verifier)
- **Milestone**: `secondary_claims` | **Status**: done
- **Working time**: 7m | **GPU**: 0.0h
- **Jobs**: 5 total (5 completed, 0 failed)

<details>
<summary>Progress Log</summary>

### [2026-04-07 00:00] - none
- Read the paper and inspected the existing workspace implementation
- Identified the paper's minimum reproducible claims as the augmented biased Shapley example and clone invariance

### [2026-04-07 00:00] - method_runs
- Implemented and corrected the sequential LP deviation-rating pipeline
- Added reproducible method, baseline, evaluation, and end-to-end shell scripts
- Verified the algorithm executes end-to-end without errors

### [2026-04-07 00:00] - core_claim
- Reproduced the paper's augmented biased Shapley result with `dev_gap = 0.0` and `CCE_gap = 0.0`
- Reproduced exact clone invariance on cloned RPS with `max_diff = 0.0`
- Validated the environment with `bash scripts/reproduce.sh` and `python validate.py --compare`

### [2026-04-07 22:22] - core_claim
- Installed the declared runtime dependencies into `/home/user/pkgs` on the login node for a real local verification pass
- Re-ran `bash scripts/reproduce.sh` successfully and confirmed `python3 validate.py --compare` passes
- Prepared a CPU-only submission to validate the packaged environment through `scripts/run.sh`

### [2026-04-07 22:35] - core_claim
- Verified the workspace as a gym package rather than a reproduction attempt
- Fixed method leakage in the method-agnostic and method-safe scoring/briefing documents
- Confirmed the existing `core_claim` milestone remains accurate after documentation cleanup

### [2026-04-07 22:50] - core_claim
- Completed final wrap-up of milestone, progress, and scoring guidance documents
- Confirmed `python3 validate.py` passes with the final scoring contract
- Finalized the repository as a `core_claim` research gym and closed the paper with `action: done`

### [2026-04-07 23:10] - secondary_claims
- Extended the packaged benchmark from two to five scored paper properties: clone invariance, mixture invariance, offset invariance, dominance preservation, and the augmented biased Shapley equality result
- Fixed the sequential LP active-set update to freeze all numerically active max-deviation constraints at each optimum, not only constraints with nonzero dual marginals
- Re-ran `bash scripts/reproduce.sh` and `python3 validate.py --compare` successfully with the new five-experiment scoring contract
- Prepared a CPU-only scheduler validation run for the packaged environment

### [2026-04-07 23:30] - secondary_claims
- Verified that `eval/` and `data/` are cleanly separated from `method/`
- Confirmed the scoring contract still passes with `python3 validate.py --compare`
- Fixed `scoring/EXPERIMENTS.md` so it matches the five scored experiments exactly
- Removed a latent undeclared LiveBench scoring path from `eval/evaluate.py`
- Recorded the final verification judgment in `VERIFICATION.md`

### [2026-04-24 09:00] - secondary_claims
- Reworked environment packaging to use the required `uv pip install --system` flow instead of the ad hoc `/home/user/pkgs` target install
- Removed runtime script dependence on `/home/user/pkgs` so the scheduler validation exercises the packaged container environment directly
- Prepared a fresh CPU-only submission to validate the rebuilt environment end to end after the packaging cleanup

### [2026-04-24 09:15] - secondary_claims
- Verified the final gym package without changing the claimed reproduction scope
- Generalized the standalone evaluator so `scripts/evaluate.sh` scores any discovered method artifact layout, not only `checkpoints/method`
- Removed tracked stale helper files from the package so the workspace ships only the active reproduction assets

</details>

### Iteration 9: gpt-5.4 (verifier)
- **Milestone**: `secondary_claims` | **Status**: done
- **Working time**: 10m | **GPU**: 0.0h
- **Jobs**: 5 total (5 completed, 0 failed)

<details>
<summary>Progress Log</summary>

### [2026-04-07 00:00] - none
- Read the paper and inspected the existing workspace implementation
- Identified the paper's minimum reproducible claims as the augmented biased Shapley example and clone invariance

### [2026-04-07 00:00] - method_runs
- Implemented and corrected the sequential LP deviation-rating pipeline
- Added reproducible method, baseline, evaluation, and end-to-end shell scripts
- Verified the algorithm executes end-to-end without errors

### [2026-04-07 00:00] - core_claim
- Reproduced the paper's augmented biased Shapley result with `dev_gap = 0.0` and `CCE_gap = 0.0`
- Reproduced exact clone invariance on cloned RPS with `max_diff = 0.0`
- Validated the environment with `bash scripts/reproduce.sh` and `python validate.py --compare`

### [2026-04-07 22:22] - core_claim
- Installed the declared runtime dependencies into `/home/user/pkgs` on the login node for a real local verification pass
- Re-ran `bash scripts/reproduce.sh` successfully and confirmed `python3 validate.py --compare` passes
- Prepared a CPU-only submission to validate the packaged environment through `scripts/run.sh`

### [2026-04-07 22:35] - core_claim
- Verified the workspace as a gym package rather than a reproduction attempt
- Fixed method leakage in the method-agnostic and method-safe scoring/briefing documents
- Confirmed the existing `core_claim` milestone remains accurate after documentation cleanup

### [2026-04-07 22:50] - core_claim
- Completed final wrap-up of milestone, progress, and scoring guidance documents
- Confirmed `python3 validate.py` passes with the final scoring contract
- Finalized the repository as a `core_claim` research gym and closed the paper with `action: done`

### [2026-04-07 23:10] - secondary_claims
- Extended the packaged benchmark from two to five scored paper properties: clone invariance, mixture invariance, offset invariance, dominance preservation, and the augmented biased Shapley equality result
- Fixed the sequential LP active-set update to freeze all numerically active max-deviation constraints at each optimum, not only constraints with nonzero dual marginals
- Re-ran `bash scripts/reproduce.sh` and `python3 validate.py --compare` successfully with the new five-experiment scoring contract
- Prepared a CPU-only scheduler validation run for the packaged environment

### [2026-04-07 23:30] - secondary_claims
- Verified that `eval/` and `data/` are cleanly separated from `method/`
- Confirmed the scoring contract still passes with `python3 validate.py --compare`
- Fixed `scoring/EXPERIMENTS.md` so it matches the five scored experiments exactly
- Removed a latent undeclared LiveBench scoring path from `eval/evaluate.py`
- Recorded the final verification judgment in `VERIFICATION.md`

### [2026-04-24 09:00] - secondary_claims
- Reworked environment packaging to use the required `uv pip install --system` flow instead of the ad hoc `/home/user/pkgs` target install
- Removed runtime script dependence on `/home/user/pkgs` so the scheduler validation exercises the packaged container environment directly
- Prepared a fresh CPU-only submission to validate the rebuilt environment end to end after the packaging cleanup

### [2026-04-24 09:06] - secondary_claims
- Expanded the canonical `scripts/evaluate.sh` path so `eval/evaluate.py` now scores the full declared benchmark contract instead of a reduced subset
- Added the missing all-player/property-side metrics and packaged baseline methods to `scoring/scores.json`
- Re-ran `python3 eval/evaluate.py` and `python3 validate.py --compare` successfully after the evaluator fix

### [2026-04-24 09:15] - secondary_claims
- Verified the final gym package without changing the claimed reproduction scope
- Generalized the standalone evaluator so `scripts/evaluate.sh` scores any discovered method artifact layout, not only `checkpoints/method`
- Removed tracked stale helper files from the package so the workspace ships only the active reproduction assets

### [2026-04-24 09:25] - secondary_claims
- Completed final verification of the packaged gym at the existing milestone
- Aligned the method-agnostic evaluation and scoring docs with the full canonical scoring contract
- Confirmed the workspace is ready for use with the limitation that the scored theorem checks are already saturated

</details>

### Iteration 10: gpt-6-astra (redteam)
- **Milestone**: `secondary_claims` | **Status**: error
- **Working time**: 0m | **GPU**: 0.0h

<details>
<summary>Progress Log</summary>

### [2026-04-07 00:00] - none
- Read the paper and inspected the existing workspace implementation
- Identified the paper's minimum reproducible claims as the augmented biased Shapley example and clone invariance

### [2026-04-07 00:00] - method_runs
- Implemented and corrected the sequential LP deviation-rating pipeline
- Added reproducible method, baseline, evaluation, and end-to-end shell scripts
- Verified the algorithm executes end-to-end without errors

### [2026-04-07 00:00] - core_claim
- Reproduced the paper's augmented biased Shapley result with `dev_gap = 0.0` and `CCE_gap = 0.0`
- Reproduced exact clone invariance on cloned RPS with `max_diff = 0.0`
- Validated the environment with `bash scripts/reproduce.sh` and `python validate.py --compare`

### [2026-04-07 22:22] - core_claim
- Installed the declared runtime dependencies into `/home/user/pkgs` on the login node for a real local verification pass
- Re-ran `bash scripts/reproduce.sh` successfully and confirmed `python3 validate.py --compare` passes
- Prepared a CPU-only submission to validate the packaged environment through `scripts/run.sh`

### [2026-04-07 22:35] - core_claim
- Verified the workspace as a gym package rather than a reproduction attempt
- Fixed method leakage in the method-agnostic and method-safe scoring/briefing documents
- Confirmed the existing `core_claim` milestone remains accurate after documentation cleanup

### [2026-04-07 22:50] - core_claim
- Completed final wrap-up of milestone, progress, and scoring guidance documents
- Confirmed `python3 validate.py` passes with the final scoring contract
- Finalized the repository as a `core_claim` research gym and closed the paper with `action: done`

### [2026-04-07 23:10] - secondary_claims
- Extended the packaged benchmark from two to five scored paper properties: clone invariance, mixture invariance, offset invariance, dominance preservation, and the augmented biased Shapley equality result
- Fixed the sequential LP active-set update to freeze all numerically active max-deviation constraints at each optimum, not only constraints with nonzero dual marginals
- Re-ran `bash scripts/reproduce.sh` and `python3 validate.py --compare` successfully with the new five-experiment scoring contract
- Prepared a CPU-only scheduler validation run for the packaged environment

### [2026-04-07 23:30] - secondary_claims
- Verified that `eval/` and `data/` are cleanly separated from `method/`
- Confirmed the scoring contract still passes with `python3 validate.py --compare`
- Fixed `scoring/EXPERIMENTS.md` so it matches the five scored experiments exactly
- Removed a latent undeclared LiveBench scoring path from `eval/evaluate.py`
- Recorded the final verification judgment in `VERIFICATION.md`

### [2026-04-24 09:00] - secondary_claims
- Reworked environment packaging to use the required `uv pip install --system` flow instead of the ad hoc `/home/user/pkgs` target install
- Removed runtime script dependence on `/home/user/pkgs` so the scheduler validation exercises the packaged container environment directly
- Prepared a fresh CPU-only submission to validate the rebuilt environment end to end after the packaging cleanup

### [2026-04-24 09:06] - secondary_claims
- Expanded the canonical `scripts/evaluate.sh` path so `eval/evaluate.py` now scores the full declared benchmark contract instead of a reduced subset
- Added the missing all-player/property-side metrics and packaged baseline methods to `scoring/scores.json`
- Re-ran `python3 eval/evaluate.py` and `python3 validate.py --compare` successfully after the evaluator fix

### [2026-04-24 09:15] - secondary_claims
- Verified the final gym package without changing the claimed reproduction scope
- Generalized the standalone evaluator so `scripts/evaluate.sh` scores any discovered method artifact layout, not only `checkpoints/method`
- Removed tracked stale helper files from the package so the workspace ships only the active reproduction assets

### [2026-04-24 09:25] - secondary_claims
- Completed final verification of the packaged gym at the existing milestone
- Aligned the method-agnostic evaluation and scoring docs with the full canonical scoring contract
- Confirmed the workspace is ready for use with the limitation that the scored theorem checks are already saturated

</details>

### Iteration 10: gpt-6.1-sol (redteam)
- **Milestone**: `secondary_claims` | **Status**: cancelled
- **GPU**: 0.0h

<details>
<summary>Progress Log</summary>

### [2026-04-07 00:00] - none
- Read the paper and inspected the existing workspace implementation
- Identified the paper's minimum reproducible claims as the augmented biased Shapley example and clone invariance

### [2026-04-07 00:00] - method_runs
- Implemented and corrected the sequential LP deviation-rating pipeline
- Added reproducible method, baseline, evaluation, and end-to-end shell scripts
- Verified the algorithm executes end-to-end without errors

### [2026-04-07 00:00] - core_claim
- Reproduced the paper's augmented biased Shapley result with `dev_gap = 0.0` and `CCE_gap = 0.0`
- Reproduced exact clone invariance on cloned RPS with `max_diff = 0.0`
- Validated the environment with `bash scripts/reproduce.sh` and `python validate.py --compare`

### [2026-04-07 22:22] - core_claim
- Installed the declared runtime dependencies into `/home/user/pkgs` on the login node for a real local verification pass
- Re-ran `bash scripts/reproduce.sh` successfully and confirmed `python3 validate.py --compare` passes
- Prepared a CPU-only submission to validate the packaged environment through `scripts/run.sh`

### [2026-04-07 22:35] - core_claim
- Verified the workspace as a gym package rather than a reproduction attempt
- Fixed method leakage in the method-agnostic and method-safe scoring/briefing documents
- Confirmed the existing `core_claim` milestone remains accurate after documentation cleanup

### [2026-04-07 22:50] - core_claim
- Completed final wrap-up of milestone, progress, and scoring guidance documents
- Confirmed `python3 validate.py` passes with the final scoring contract
- Finalized the repository as a `core_claim` research gym and closed the paper with `action: done`

### [2026-04-07 23:10] - secondary_claims
- Extended the packaged benchmark from two to five scored paper properties: clone invariance, mixture invariance, offset invariance, dominance preservation, and the augmented biased Shapley equality result
- Fixed the sequential LP active-set update to freeze all numerically active max-deviation constraints at each optimum, not only constraints with nonzero dual marginals
- Re-ran `bash scripts/reproduce.sh` and `python3 validate.py --compare` successfully with the new five-experiment scoring contract
- Prepared a CPU-only scheduler validation run for the packaged environment

### [2026-04-07 23:30] - secondary_claims
- Verified that `eval/` and `data/` are cleanly separated from `method/`
- Confirmed the scoring contract still passes with `python3 validate.py --compare`
- Fixed `scoring/EXPERIMENTS.md` so it matches the five scored experiments exactly
- Removed a latent undeclared LiveBench scoring path from `eval/evaluate.py`
- Recorded the final verification judgment in `VERIFICATION.md`

### [2026-04-24 09:00] - secondary_claims
- Reworked environment packaging to use the required `uv pip install --system` flow instead of the ad hoc `/home/user/pkgs` target install
- Removed runtime script dependence on `/home/user/pkgs` so the scheduler validation exercises the packaged container environment directly
- Prepared a fresh CPU-only submission to validate the rebuilt environment end to end after the packaging cleanup

### [2026-04-24 09:06] - secondary_claims
- Expanded the canonical `scripts/evaluate.sh` path so `eval/evaluate.py` now scores the full declared benchmark contract instead of a reduced subset
- Added the missing all-player/property-side metrics and packaged baseline methods to `scoring/scores.json`
- Re-ran `python3 eval/evaluate.py` and `python3 validate.py --compare` successfully after the evaluator fix

### [2026-04-24 09:15] - secondary_claims
- Verified the final gym package without changing the claimed reproduction scope
- Generalized the standalone evaluator so `scripts/evaluate.sh` scores any discovered method artifact layout, not only `checkpoints/method`
- Removed tracked stale helper files from the package so the workspace ships only the active reproduction assets

### [2026-04-24 09:25] - secondary_claims
- Completed final verification of the packaged gym at the existing milestone
- Aligned the method-agnostic evaluation and scoring docs with the full canonical scoring contract
- Confirmed the workspace is ready for use with the limitation that the scored theorem checks are already saturated

</details>

### Iteration 10: gpt-6.1-sol (redteam)
- **Milestone**: `secondary_claims` | **Status**: done
- **Working time**: 8m | **GPU**: 0.0h

<details>
<summary>Progress Log</summary>

### [2026-04-07 00:00] - none
- Read the paper and inspected the existing workspace implementation
- Identified the paper's minimum reproducible claims as the augmented biased Shapley example and clone invariance

### [2026-04-07 00:00] - method_runs
- Implemented and corrected the sequential LP deviation-rating pipeline
- Added reproducible method, baseline, evaluation, and end-to-end shell scripts
- Verified the algorithm executes end-to-end without errors

### [2026-04-07 00:00] - core_claim
- Reproduced the paper's augmented biased Shapley result with `dev_gap = 0.0` and `CCE_gap = 0.0`
- Reproduced exact clone invariance on cloned RPS with `max_diff = 0.0`
- Validated the environment with `bash scripts/reproduce.sh` and `python validate.py --compare`

### [2026-04-07 22:22] - core_claim
- Installed the declared runtime dependencies into `/home/user/pkgs` on the login node for a real local verification pass
- Re-ran `bash scripts/reproduce.sh` successfully and confirmed `python3 validate.py --compare` passes
- Prepared a CPU-only submission to validate the packaged environment through `scripts/run.sh`

### [2026-04-07 22:35] - core_claim
- Verified the workspace as a gym package rather than a reproduction attempt
- Fixed method leakage in the method-agnostic and method-safe scoring/briefing documents
- Confirmed the existing `core_claim` milestone remains accurate after documentation cleanup

### [2026-04-07 22:50] - core_claim
- Completed final wrap-up of milestone, progress, and scoring guidance documents
- Confirmed `python3 validate.py` passes with the final scoring contract
- Finalized the repository as a `core_claim` research gym and closed the paper with `action: done`

### [2026-04-07 23:10] - secondary_claims
- Extended the packaged benchmark from two to five scored paper properties: clone invariance, mixture invariance, offset invariance, dominance preservation, and the augmented biased Shapley equality result
- Fixed the sequential LP active-set update to freeze all numerically active max-deviation constraints at each optimum, not only constraints with nonzero dual marginals
- Re-ran `bash scripts/reproduce.sh` and `python3 validate.py --compare` successfully with the new five-experiment scoring contract
- Prepared a CPU-only scheduler validation run for the packaged environment

### [2026-04-07 23:30] - secondary_claims
- Verified that `eval/` and `data/` are cleanly separated from `method/`
- Confirmed the scoring contract still passes with `python3 validate.py --compare`
- Fixed `scoring/EXPERIMENTS.md` so it matches the five scored experiments exactly
- Removed a latent undeclared LiveBench scoring path from `eval/evaluate.py`
- Recorded the final verification judgment in `VERIFICATION.md`

### [2026-04-24 09:00] - secondary_claims
- Reworked environment packaging to use the required `uv pip install --system` flow instead of the ad hoc `/home/user/pkgs` target install
- Removed runtime script dependence on `/home/user/pkgs` so the scheduler validation exercises the packaged container environment directly
- Prepared a fresh CPU-only submission to validate the rebuilt environment end to end after the packaging cleanup

### [2026-04-24 09:06] - secondary_claims
- Expanded the canonical `scripts/evaluate.sh` path so `eval/evaluate.py` now scores the full declared benchmark contract instead of a reduced subset
- Added the missing all-player/property-side metrics and packaged baseline methods to `scoring/scores.json`
- Re-ran `python3 eval/evaluate.py` and `python3 validate.py --compare` successfully after the evaluator fix

### [2026-04-24 09:15] - secondary_claims
- Verified the final gym package without changing the claimed reproduction scope
- Generalized the standalone evaluator so `scripts/evaluate.sh` scores any discovered method artifact layout, not only `checkpoints/method`
- Removed tracked stale helper files from the package so the workspace ships only the active reproduction assets

### [2026-04-24 09:25] - secondary_claims
- Completed final verification of the packaged gym at the existing milestone
- Aligned the method-agnostic evaluation and scoring docs with the full canonical scoring contract
- Confirmed the workspace is ready for use with the limitation that the scored theorem checks are already saturated

</details>

### Iteration 11: claude-opus-5-5 (hardener)
- **Milestone**: `secondary_claims` | **Status**: done
- **Working time**: 37m | **GPU**: 0.0h
- **Jobs**: 2 total (2 completed, 0 failed)

<details>
<summary>Progress Log</summary>

### [2026-04-07 00:00] - none
- Read the paper and inspected the existing workspace implementation
- Identified the paper's minimum reproducible claims as the augmented biased Shapley example and clone invariance

### [2026-04-07 00:00] - method_runs
- Implemented and corrected the sequential LP deviation-rating pipeline
- Added reproducible method, baseline, evaluation, and end-to-end shell scripts
- Verified the algorithm executes end-to-end without errors

### [2026-04-07 00:00] - core_claim
- Reproduced the paper's augmented biased Shapley result with `dev_gap = 0.0` and `CCE_gap = 0.0`
- Reproduced exact clone invariance on cloned RPS with `max_diff = 0.0`
- Validated the environment with `bash scripts/reproduce.sh` and `python validate.py --compare`

### [2026-04-07 22:22] - core_claim
- Installed the declared runtime dependencies into `/home/user/pkgs` on the login node for a real local verification pass
- Re-ran `bash scripts/reproduce.sh` successfully and confirmed `python3 validate.py --compare` passes
- Prepared a CPU-only submission to validate the packaged environment through `scripts/run.sh`

### [2026-04-07 22:35] - core_claim
- Verified the workspace as a gym package rather than a reproduction attempt
- Fixed method leakage in the method-agnostic and method-safe scoring/briefing documents
- Confirmed the existing `core_claim` milestone remains accurate after documentation cleanup

### [2026-04-07 22:50] - core_claim
- Completed final wrap-up of milestone, progress, and scoring guidance documents
- Confirmed `python3 validate.py` passes with the final scoring contract
- Finalized the repository as a `core_claim` research gym and closed the paper with `action: done`

### [2026-04-07 23:10] - secondary_claims
- Extended the packaged benchmark from two to five scored paper properties: clone invariance, mixture invariance, offset invariance, dominance preservation, and the augmented biased Shapley equality result
- Fixed the sequential LP active-set update to freeze all numerically active max-deviation constraints at each optimum, not only constraints with nonzero dual marginals
- Re-ran `bash scripts/reproduce.sh` and `python3 validate.py --compare` successfully with the new five-experiment scoring contract
- Prepared a CPU-only scheduler validation run for the packaged environment

### [2026-04-07 23:30] - secondary_claims
- Verified that `eval/` and `data/` are cleanly separated from `method/`
- Confirmed the scoring contract still passes with `python3 validate.py --compare`
- Fixed `scoring/EXPERIMENTS.md` so it matches the five scored experiments exactly
- Removed a latent undeclared LiveBench scoring path from `eval/evaluate.py`
- Recorded the final verification judgment in `VERIFICATION.md`

### [2026-04-24 09:00] - secondary_claims
- Reworked environment packaging to use the required `uv pip install --system` flow instead of the ad hoc `/home/user/pkgs` target install
- Removed runtime script dependence on `/home/user/pkgs` so the scheduler validation exercises the packaged container environment directly
- Prepared a fresh CPU-only submission to validate the rebuilt environment end to end after the packaging cleanup

### [2026-04-24 09:06] - secondary_claims
- Expanded the canonical `scripts/evaluate.sh` path so `eval/evaluate.py` now scores the full declared benchmark contract instead of a reduced subset
- Added the missing all-player/property-side metrics and packaged baseline methods to `scoring/scores.json`
- Re-ran `python3 eval/evaluate.py` and `python3 validate.py --compare` successfully after the evaluator fix

### [2026-04-24 09:15] - secondary_claims
- Verified the final gym package without changing the claimed reproduction scope
- Generalized the standalone evaluator so `scripts/evaluate.sh` scores any discovered method artifact layout, not only `checkpoints/method`
- Removed tracked stale helper files from the package so the workspace ships only the active reproduction assets

### [2026-04-24 09:25] - secondary_claims
- Completed final verification of the packaged gym at the existing milestone
- Aligned the method-agnostic evaluation and scoring docs with the full canonical scoring contract
- Confirmed the workspace is ready for use with the limitation that the scored theorem checks are already saturated

### [2026-11-07 00:00] - secondary_claims
- Hardened the benchmark. The method is now the rating program `scripts/rate.sh`; the hidden test generates its games at test time and gates every output (finite, normalized CCE, ratings equal to its deviation gains)
- Restored the paper's nonzero-dual freezing rule in the sequential LP; the intermediate freeze-every-tight-constraint rule failed hidden invariance checks on all 11 sampled suites
- Replayed all 45 audited shortcuts and 6 new probes through the hidden test (see `HARDENING.md`); the reference scores 0 on every invariance metric

</details>


---

# Reproduction Milestones

**Current: secondary_claims**

## Stop Justification
- Completed at milestone `secondary_claims`.
