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
