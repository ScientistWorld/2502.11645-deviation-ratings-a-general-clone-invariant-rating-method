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
- **Be efficiently computable**: polynomial time in the size of the game, and practical on games with a thousand or more joint strategies
- **Be directional**: when a rating is used to decide which strategies to keep in an evolving population, the population should move toward an equilibrium of the underlying game rather than toward strategies that only look good on average

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

The paper reports using CVXPY with GLOP (OR-Tools' simplex solver) as the backend. This reproduction keeps the same sequential-LP algorithm but implements it with SciPy's `linprog` (HiGHS backend) instead of CVXPY/GLOP (`method/deviation_rating.py`). The benchmark calls it through the rating program `scripts/rate.sh` -> `method/rate.py`. For every game, that program returns the final LP's distribution and its deviation gains as the ratings.

Numerical care (paper Appendix B: "care needs to be taken to minimize the accumulation of errors"):
- **Scaling.** Deviation coefficients are divided by the payoff scale and quantized to 14 decimals, so solver tolerances are relative.
- **Fallback when an LP is reported infeasible.** Frozen ratings are imposed as equalities. On some Sheriff population meta-games and games with about 1,000 joint actions, round-off accumulated over many iterations made a later LP infeasible. Only then is the iteration re-solved, first with each frozen gain held in a narrow band (relative half-width 1e-9 to 1e-7). If that also fails, the frozen gains are re-centred on the previous iteration's distribution, which satisfies them by construction.
- **Time limit.** Each LP solve has a 60 s time limit.
- None of this changes the selection in exact arithmetic. On the benchmark's games the fallback is rarely or never needed (0 fallback solves on the hidden population run).

An earlier version also froze every constraint that happened to be numerically tight at the vertex the solver returned. When the optimal face is not a single point, for example when one player's best action pins epsilon at 0, that freezes ratings that later iterations should lower. The result then depends on the solver's vertex choice and loses uniqueness and invariance. The current default follows the paper's nonzero-dual rule (`freeze_rule="dual"`); the old rule is kept only as a diagnostic (`freeze_rule="active"`).

The algorithm still runs in polynomial time since it solves sequential LPs, each in polynomial time. The maximum number of outer iterations is $\sum_p |A_p|$ (number of constraints).

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

**Secondary**: On cyclic games (Shapley's game), deviation rating gives equal ratings to all strategies in the cycle. On LLM evaluation (Livebench), deviation rating groups top models by niche rather than forcing a linear ranking. Used as the fitness measure of a population search in the general-sum Sheriff game, deviation ratings reduce the full-game CCE gap where uniform averaging stalls (Section 5.3, Figure 3b).

---

# Evaluation

How success is measured for a game-theoretic rating method.

## How a method is scored

A method is a **rating program**: `bash scripts/rate.sh GAMES_JSON RATINGS_JSON`. The evaluators write the games, run the program, and score what it returns. Methods never get the scored games ahead of time: the hidden test generates its games when it runs.

Input (written by the evaluator):

```json
{"games": [{"id": "<opaque id>", "payoffs": P}, ...]}
```

`P` has shape `[N][A_1]...[A_N]`: `P[p][a_1]...[a_N]` is player `p`'s payoff at the joint action `(a_1, ..., a_N)`. Games have 2 to 5 players, can include players with a single action, and range from 2x2 up to about 2,400 joint actions.

Output (written by the method):

```json
{"results": {"<id>": {"ratings": [[r_0(0), r_0(1), ...], [r_1(0), ...], ...],
                      "equilibrium": [s_0, s_1, ...]}}}
```

`ratings[p][a]` is the rating of player `p`'s action `a`. `equilibrium` is the joint recommendation distribution the ratings come from, as a flat list of `A_1 * ... * A_N` probabilities in C (row-major) order.

### Calls

The program is called many times per evaluation: once per iteration of the population experiment (96 calls). Each call carries that iteration's population meta-games plus a share of the property games, shuffled and anonymised. The two games of an invariance pair (a game and its cloned, mixed or offset copy) are always in **different** calls. Each call runs in a fresh temporary directory (also `$TMPDIR`). A call may take at most 300 s, and all calls together at most 2400 s.

Calls must be **stateless**. Inside the job container a call fails if it creates, changes or deletes any file outside its temporary directory: in the workspace, `/tmp`, `/var/tmp` or `/dev/shm`. Every process a call starts is killed before its output is read. The hidden test also stops every other process of the submission before it begins. So one call cannot learn which games another call saw.

### Validity gates

Every game's output must pass all of these:

- every rating and probability is a finite JSON number (no `NaN`, `Infinity`, strings, booleans or nulls), with exactly one rating per action of every player;
- the distribution is non-negative and sums to 1 (tolerance 1e-6);
- the distribution is a coarse correlated equilibrium: every deviation gain `sum_a s(a) [G_p(a'_p, a_-p) - G_p(a)]` is at most `1e-6 * scale`;
- the ratings **are** those deviation gains of the submitted distribution, within `1e-6 * scale`.

Here `scale = max(1, largest absolute payoff in the game)`. If any game fails a gate, every experiment containing that game is **scored as failed**: its lower-is-better metrics are set to `1e6` and `min_margin` to `-1e6`. A crashed, timed-out, stateful or malformed call fails every game it carried. A failure on any population meta-game fails the population experiment.

Every scored number is recomputed from the payoffs and the submitted distribution. Numbers the method reports are only compared against these recomputed values, never used directly. Rating differences of at most `1e-6 * scale` count as 0, and metrics are rounded to 6 decimals.

### Evaluators

| Command | Games | Output |
|---|---|---|
| `bash scripts/evaluate.sh` | the five documented public games plus families generated from a visible seed, and the population experiment on a visible seed | `scoring/scores.json` |
| `bash scripts/evaluate_train.sh` | the same visible suite | `scoring/scores_train.json` |
| `bash scripts/evaluate_test.sh` (hidden, no arguments) | about 250 property games and the population experiment, all generated at test time from a seed that exists only in the hidden test | `scoring/scores_test.json` |

The evaluators run with `python3 -I`, ignoring `PYTHONPATH`, user site-packages and the working directory. They do not read `checkpoints/`, `data/`, `baseline/` or `scoring/reference.json`. Baselines are computed by the evaluator itself. One evaluation takes about 4-4.5 minutes with the reproduced method, mostly program start-up across the 96 calls.

## Experiments

Property experiments: each metric is a maximum over the experiment's games (dominance violations are summed). Lower is better except `min_margin`. Every property experiment also reports `strictness_gap` (see below).

1. **`biased_shapley_augmented`: no artificial order in cyclic games.**
   - Public game: the paper's Table 2 biased Shapley game augmented with its Nash mixture `N`.
   - Hidden games are games whose deviation ratings are provably all equal:
     - the biased Shapley game with and without `N`;
     - symmetric populations of random mixtures of R/P/S, including ones with 33 and 48 strategies per player;
     - scaled, offset, cloned and relabeled variants, and variants with one or two extra bystander players (see below);
     - zero-sum rock-paper-scissors, randomly weighted RPS, and RPS-lizard-Spock.
   - `dev_gap`: rating spread of the first cyclic player's actions.
   - `all_player_dev_gap`: spread across both cyclic players.
   - `player_symmetry_gap`: largest same-strategy mismatch between the two players.
   - `CCE_gap`: total CCE regret of the submitted distribution.

2. **`clone_invariance`: duplicating a strategy changes nothing.**
   - Public game: rock-paper-scissors with player 1's rock cloned.
   - Hidden games: random 2- and 3-player general-sum, zero-sum and common-interest games, games with one or two bystanders, products of two independent 2-player games (with or without a bystander), meta-games of random Sheriff populations (as in experiment 6), and 3-player games above 1,000 and above 2,000 joint actions. Each gets a clone of one action inserted at a random position, and every player's actions are relabeled.
   - `max_diff`: change in the ratings of the other players' strategies, the ones that face the clone.
   - `all_players_max_diff`: change over all original actions of all players.
   - `clone_source_gap`: clone's rating versus its source.

3. **`mixture_invariance`: adding a mixed strategy changes nothing, and the mixture gets the mixed rating.**
   - The evaluator fixes the mixture weights: `[0.3, 0.7]` on the public general-sum game, and random weights over 2-4 actions on the hidden games (same game kinds as above).
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
   - `min_margin`: smallest ratio of rating advantage to guaranteed payoff advantage. On a constant-gap pair this ratio is exactly 1 for any rating that is the deviation gain of some distribution, so it cannot exceed 1. It shows whether a method stays in units of payoff, not how far it separates actions.
   - `CCE_gap`: total CCE regret of the submitted distribution.

6. **`population_improvement`: ratings that drive improvement (paper Section 5.3).**
   - Game: Sheriff, a 2-player general-sum bargaining game (item penalty 1, item value 5, max bribe 2, max items 10, 2 rounds, sheriff penalty 1).
   - Each of 8 independent runs keeps 8 random stochastic policies per player. Every iteration:
     - the evaluator sends the population's 8x8 meta-game (expected payoffs, actions relabeled) to the rating program;
     - it discards each player's 2 lowest-rated policies, breaking ties within `1e-6 * scale` at random;
     - it replaces them with the next policies from a fixed random stream.
   - Every 8 iterations, over 96 iterations, the evaluator measures the population's full-game CCE gap under the meta-game's maximum-entropy CCE: the sum over players of the best deviation gain over all Sheriff policies. Everything except the ratings is fixed by the evaluator, so every method faces the same draws.
   - `late_gap_ratio` (primary): mean gap over the second half of the run divided by the initial gap, averaged over runs.
   - `mean_gap_ratio`: the same over all checkpoints.
   - Lower is better; 1 means no progress. Neither metric is bounded by any known method's value.

### `strictness_gap`

The selection being tested is the strictest equilibrium: minimize the largest deviation gain, then the next largest, and so on. `strictness_gap` checks it at every level the evaluator can certify.

- **Top level.** For every property game the evaluator computes the smallest largest deviation gain any CCE attains, `min over CCEs of max over (p, a')` of the deviation gain. It solves this matrix-game value as a linear program and certifies it with a dual bound.
- **Independent blocks.** Some hidden games are products of independent sub-games: groups of players whose payoffs, up to offsets `b_p(a_-p)`, depend only on their own group's actions (bystanders below, and pairs of independent 2-player games). A block's deviation gains depend only on the distribution's marginal on that block, so the strictest equilibrium of the whole game is also strictest on every block. For every block the evaluator computes and certifies the block's own `min over CCEs of max over (p in block, a')`.
- **The metric.** `strictness_gap` is the largest excess, over the experiment's games and blocks, of the submitted distribution's largest deviation gain within the block over that minimum.

0 means the selected equilibrium is as strict as possible on every certified block. All blocks except the one with the largest minimum sit below the top of the lexicographic order. A selection that is strict only at the top level and stops refining below it, or a less strict equilibrium (for example one where every gain is 0), shows up here even when the result is invariant. Baselines are measured with their uniform distribution.

### Bystander players

Some hidden games add one or two players whose payoff depends only on their own action (3-10 actions each). Such a player does not change the other players' deviation ratings. Its best action has deviation gain 0 under every CCE, though, which pins the first "minimize the largest deviation gain" LP at 0. Most of its other actions' gains lie between 0 and the original players' strictest value, so the original players' strictest equilibrium is reached only after many further selection steps, one per such level. A method must keep selecting among the remaining equilibria until every gain is fixed.

## Baselines

All baselines are computed by the evaluator on the same games, never by the submission:

- `uniform_payoff` (every experiment): mean payoff over all opponent profiles. Its CCE and strictness gaps are those of the uniform joint distribution. In the population experiment it drops the policies with the lowest mean payoff.
- `zero_rating` and `negative_uniform_payoff` (dominance only): constant zero ratings and negated uniform ratings.
- `random_selection` (population only): drops random policies.

Baseline rows are reference points and are not subject to the method gates.

## What the test does and does not establish

The property experiments check the properties the paper proves (Table 1 and Section 5.1), and the strictness of the selected equilibrium at the top level and on every independent block, on games no submission can see beforehand. They do not check which algorithm produced the distribution. Below the top level, strictness is certified directly only on product games, through their blocks. Within a game that has no product structure, equilibria that differ only below the top level are distinguished through the invariance checks, not directly.

The population experiment measures how well a rating drives a simple evolutionary search, the paper's directional claim. Only there can a method score better than the reproduced method. A method that changes its equilibrium selection to do so will usually pay for it in `strictness_gap` or the invariance metrics, which is the trade-off the benchmark is meant to expose.

## Packaged scope

The paper's LiveBench and Atari analyses and the 3-player Kuhn poker run of Section 5.3 are not part of the scored benchmark.

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

### Iteration 11: claude-opus-5-5 (hardener)
- **Milestone**: `secondary_claims` | **Status**: cancelled
- **GPU**: 0.0h
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

### Iteration 10: gpt-6.1-sol (redteam)
- **Milestone**: `secondary_claims` | **Status**: done
- **Working time**: 13m | **GPU**: 0.0h
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

### Iteration 11: claude-opus-5-5 (hardener)
- **Milestone**: `secondary_claims` | **Status**: done
- **Working time**: 60m | **GPU**: 0.0h
- **Jobs**: 8 total (7 completed, 1 failed)

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

### Iteration 10: gpt-6.1-sol (redteam)
- **Milestone**: `secondary_claims` | **Status**: done
- **Working time**: 9m | **GPU**: 0.0h
- **Jobs**: 10 total (9 completed, 1 failed)

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

### Iteration 11: claude-opus-5-5 (hardener)
- **Milestone**: `secondary_claims` | **Status**: done
- **Working time**: 23m | **GPU**: 0.0h
- **Jobs**: 12 total (10 completed, 2 failed)

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
