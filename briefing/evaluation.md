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

The evaluators run with `python3 -I`, ignoring `PYTHONPATH`, user site-packages and the working directory. They do not read `checkpoints/`, `data/`, `baseline/` or `scoring/reference.json`. Baselines are computed by the evaluator itself. One visible evaluation takes about 3.5 minutes with the reproduced method, mostly program start-up across the 96 calls.

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
