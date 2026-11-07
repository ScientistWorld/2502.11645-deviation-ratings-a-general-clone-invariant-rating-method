# Hardening report (iteration 13, final)

## Summary

`REDTEAM.md` found two shortcuts that tied the reference on all 22 hidden metrics:
- **three_lp_shortcut** stops Algorithm 1 after three LP rounds.
- **size_abandonment_shortcut** returns nothing for games above 2,048 joint actions.

The audit also found that `strictness_gap` only certified the *top* of the lexicographic order the paper's selection minimises. The bystander players then in the test had at most 3 actions, so three rounds always reached the other players' strictest value.

Both shortcuts are now closed:
- **Three-LP shortcut:** scores worse than the reference in all five property experiments.
- **Size-abandonment shortcut:** is scored as failed in all five.
- **The reference** is unchanged: 0 on every property metric, `min_margin` 1, population 0.576602 / 0.646034. Five hidden runs are byte-identical.

Better results now score higher in a clean order of how much of the algorithm runs:

| | one LP | two LPs | three LPs | full algorithm |
|---|---|---|---|---|
| Cyclic `strictness_gap` | 2.82 | 2.82 | 2.26 | 0 |
| Dominance `strictness_gap` | 0.66 | 0.63 | 0.56 | 0 |

Hidden test SHA-256: before `68494d8f…a200bf9`, after `acb833a426208a9bebe3dccfe842b42f3e91d0575b3ec4bae2931ffa1b19d45a`.

## What changed

| ID | Fix | Where |
|---|---|---|
| B | **`strictness_gap` is certified on every independent block of players.** Some games are products of independent sub-games. In each block, players' payoffs, up to offsets `b_p(a_-p)`, depend only on the block's own actions. A block's deviation gains depend only on the distribution's marginal on that block, and the blocks' marginals can be chosen independently. So the lexicographically strictest gain vector is the merge of each block's own strictest vector: within every block, the largest gain equals that block's own min-max value. Each value is one well-posed LP, solved and certified by its dual bound like the top level was. The metric is now the largest excess over games *and blocks*. Blocks below the game's top sit deeper in the lexicographic order. This avoids re-solving the degenerate LP chain, which iteration 12 rejected as ill-posed in floating point. | `block_strictness`, `strictness_gap`, `strictest_epsilon(game, players)` |
| D | **Deeper bystanders and product games.** Bystanders now have 3-10 actions. Their gain levels are fractions of the base game's strictest value: 18 of 22 lie between 0 and that value, 4 below it. So the original players' value is reached only after one LP round per level above it. New kinds: `bb4` (a base with a strict CCE plus two bystanders), `pr4` (two independent 2-player games), `pb5` (`pr4` plus a bystander), and a cyclic game with two bystanders. Planted dominated actions only touch their own block. A check over all 78 product games in each suite found 0 violations of block independence; it reports 187 with an injected dependence. On the hidden suite, every property experiment contains blocks that need at least 4 rounds; the deepest needs about 11. | `_with_bystander`, `_product_game`, `_random_game`, `_plant_dominated_action` |
| L | **Games above 2,048 joint actions in every property experiment:** 3-player games of 2,184-2,366 joint actions (`XL3`), and a 48-strategy cyclic population (2,304). The documented envelope is now 2 to 5 players, up to about 2,400 joint actions. | `LARGE_DIMS`, `_shapley_family` |
| R | **Non-blocking reaping of killed rating processes.** Bounded at 30 s. A process stuck in uninterruptible I/O keeps its pending SIGKILL and runs no more of its own code. Verification job 1 stalled for 16 minutes without output (see below). | `_kill_descendants` |

The visible protocol (`eval/protocol.py`) has the same changes. Its generators are identical apart from the seed, and it still shares no code with `eval/test/`.

Documents updated to the fixed gym: `briefing/evaluation.md`, `scoring/{TARGETS,EXPERIMENTS,CONSTRAINTS,DIRECTION}.md`, the `strictness_gap` descriptions in `scoring/reference.json`, and `DESIGN_NOTES.md`. The paper's reported numbers and all experiment weights are unchanged. The block check extends what the existing `strictness_gap` certifies (the paper's "strictest equilibrium" selection). It is not a new claim, so its weight did not need to move.

## Does a better result score higher? (variants, hidden test, proposed row)

Rerun from the final code with the REDTEAM's own candidate program and harness (copied to `redteam/hardening_final/`). Each case runs `bash scripts/evaluate_test.sh` with no arguments. Before = `redteam/current_audit/<case>/scores_test.json`, after = `redteam/hardening_final/<case>/scores_test.json`, comparison in `redteam/hardening_final/summary.json`.

| Variant | Before | After |
|---|---|---|
| Reference (seed 0, and seed 1 with permuted labels) | R | R, byte-identical to `scoring/scores_test.json` |
| Vectorized coefficient construction (honest, faster) | R | R (runtime is deliberately unscored) |
| Tighter solver tolerances (honest) | R | R |
| One-LP ablation (weaker) | worse in shapley, clone, mixture, offset; dominance tied R | **worse in all 5:** shapley `dev_gap` 3.84, strictness 2.82; clone `max_diff` 0.90, strictness 0.34; mixture drift 1.01, strictness 0.38; offset 0.64, strictness 0.28; dominance strictness 0.66 |
| Freeze-every-tight-constraint rule (weaker, new) | — | **worse in all 5:** shapley `dev_gap` 3.60, strictness 2.82; clone 0.55; mixture 0.71; offset 0.08; dominance strictness 0.66 |
| Two-LP cap | worse in shapley (1.15) and clone (0.55) only | **worse in all 5:** shapley 4.11 / strictness 2.82; clone 0.69; mixture 0.93; offset 1.76; dominance strictness 0.63 |

The population experiment ties the reference for every one of these variants: they all make the same drop decisions on the 8x8 Sheriff meta-games. Selections that differ at the *top* level do move it (iteration 12: least strict CCE 0.637, any feasible CCE 0.624).

## Major shortcuts, before and after

| Shortcut | Before | Fix | After |
|---|---|---|---|
| [three_lp_shortcut](redteam/hardening_final/three_lp_shortcut/scores_test.json) | **R on all 22 metrics** | B + D | **Worse in all 5 property experiments:** shapley `dev_gap` 3.69 / strictness 2.26; clone `max_diff` 0.32 / strictness 0.27; mixture drift 0.44, `mixture_error` 0.17 / strictness 0.34; offset 0.90 / strictness 0.27; dominance strictness 0.56. Population ties. |
| [size_abandonment_shortcut](redteam/hardening_final/size_abandonment_shortcut/scores_test.json) | **R on all 22 metrics** | L | **Failed in all 5 property experiments:** the equilibrium is missing on every hidden game above 2,048 joint actions (2,184-2,352). Population ties (8x8 games). |

The REDTEAM's public witness (paper Table 2 with an independent six-action bystander), scored with the new check in `redteam/hardening_final/witness.json`. The original players' block has certified value −2.821577.

| Mode | Original players' largest gain | `strictness_gap` |
|---|---|---|
| Reference | −2.821577 | 0 |
| Three LPs | −0.02 | 2.80 |
| Two LPs | −0.01 | 2.81 |
| One LP, or freeze-every-tight rule | 0 | 2.82 |

The other nine shortcuts in `REDTEAM.md` already scored F before. They were stopped by the validity gates, recomputation, evaluator-owned baselines and fresh score files, all unchanged, so they were not replayed. The two-LP cap above is the only one of them that was not F; it is now worse in all five experiments.

## Shortcuts and gaps left open, and why

- **A large round cap.** The deepest certified block on the hidden test needs about 11 LP rounds. A cap of 12 or more rounds would tie this test, while still being wrong on deeper games. This is a coverage limit of the same kind as the size envelope, and no finite test closes it. Such a cap saves little: it is the full algorithm on almost every game.
- **Abandoning games above about 2,400 joint actions.** This is outside the documented envelope (2 to 5 players, up to about 2,400 joint actions). It is a coverage limit, not worse quality inside the envelope.
- **Strictness below the top within a game without product structure** is still not certified directly. Such games are covered only by the invariance checks. Recomputing the full lexicographic order would need the degenerate LP chain, which is ill-posed in floating point (iteration 12).
- **Detecting the product structure and treating blocks specially.** A method could do this to pass the block check without running the full chain within each block. It would be special-casing recognizable games, which `CONSTRAINTS.md` forbids. The structure is also hidden by offsets and relabeling, and such a method would still face the invariance checks.
- **Runtime.** The vectorized variant is genuinely faster (coefficient construction 30-174x, `REDTEAM.md`) and ties. This is by design: no metric may depend on wall-clock time.
- **Iteration-12 residuals, unchanged:**
  - the stateless check has unwatched system paths;
  - the rater is not sandboxed and could read `eval/test/evaluate.py` while running;
  - the container is trusted.

## Reference score, before and after

Before: `REDTEAM.md` reference on the previous test. After: `scoring/scores_test.json`, regenerated from the final code by `scripts/run.sh`. Five runs are byte-identical: the main run, the harness's reference seed 0, seed 1 with permuted action labels, and the vectorized and tighter-tolerance variants.

| Experiment | Reference before | Reference after | Uniform baseline after |
|---|---|---|---|
| biased_shapley_augmented | all gaps 0, strictness 0 | all gaps 0, strictness 0 | dev 2.2555, all 3.5608, symmetry 2.481, CCE 4.76672, strictness 4.286515 |
| clone_invariance | 0 / 0 / 0, strictness 0 | 0 / 0 / 0, strictness 0 | 0.415752 / 0.415752 / 0, strictness 3.959754 |
| mixture_invariance | 0 / 0 / 0, strictness 0 | 0 / 0 / 0, strictness 0 | 0.343772 / 0 / 3.086416, strictness 2.688069 |
| offset_invariance | 0 / 0, strictness 0 | 0 / 0, strictness 0 | 4.088 / 2.171173, strictness 1.451191 |
| dominance_preserving | 0 violations, margin 1, CCE 0, strictness 0 | the same | uniform: 0, 1, 2.50856, strictness 2.546267; zero rating and negated uniform: 204 violations |
| population_improvement | late 0.576602, mean 0.646034 | late 0.576602, mean 0.646034 | uniform 0.667682 / 0.70202; random selection 0.968004 / 0.964801 |

The reference's property values are unchanged. The baseline rows changed because the hidden games changed.

The visible side was regenerated by the same job (`scoring/scores.json`, `scoring/scores_train.json`):
- the reference scores 0 on every property metric of the new visible suite;
- its train-seed population late gap ratio is 0.712638 (uniform 0.797493, random 1.083548), as before.

`python3 validate.py` passes.

## Headroom check

- **Property metrics: the reference sits at the bound of all 20.** Every gap and every `strictness_gap` is 0, there are 0 dominance violations, and `min_margin` is 1. This is the cap for any rating that is a distribution's deviation gain. No method can score higher on them; they are the constraint side of the paper's claim.
- **`population_improvement` (paper Section 5.3, weight 0.2) is the headroom experiment, kept from iteration 12.** The reference has a late gap ratio of 0.577 against a bound of 0. Uniform scores 0.668 and random selection 0.968, so the simple baseline is clearly below the reference on a scale with room above it.
- **The headroom is still not demonstrated.** No method tried in iterations 12 or 13 beats the reference there. Selections that differ only below the top level (one, two and three LPs, the freeze-every-tight rule) all tie it, so the experiment measures top-level selection, not the lower levels.

## Larger than seed noise

- **Reference:** deterministic. Five hidden runs are byte-identical, including one with every game's action labels permuted before solving, so solver-vertex choice does not move any score.
- **The block check:**
  - the reference's excess is 0 on all certified blocks in all five runs;
  - the shortcuts' excesses are 0.27-2.82;
  - property differences below `1e-6 * scale` count as 0.
- **Population effect over uniform:** 0.091 on the hidden seed. Iteration 12 measured it as positive on 6 of 6 paired diagnostic seeds (0.041-0.107, `redteam/population_diagnostics.json`).

## Direction of the paper's claims

- **Property claims:** the reference beats uniform averaging on cyclic equality, clone, mixture and offset invariance, CCE validity and strictness. It ties uniform on dominance, where both preserve it.
- **Section 5.3:** deviation ratings reduce the full-game gap more than uniform averaging, on the hidden seed and the train seed. The effect is smaller than in the paper's single run (paper: 0.649 vs 0.821 at the gym's horizon). The possible causes are listed in iteration 12's report: the measuring distribution of footnote 6 is unspecified, policy sampling details differ, and the paper reports one run.

## What I could not fix or explain

- **Unexplained stall.**
  - In verification job 1 (`jobs/b989d22a-7c0`), the visible evaluation finished in 261 s. The train evaluation then printed nothing for about 16 minutes, and the infrastructure killed the job ("Ray actor no longer exists").
  - The train evaluation runs the identical suite, so this was not a deterministic hang. Iteration 12 saw the same signature once. The cause is still unknown; blocked I/O on the node is the likeliest.
  - Mitigations: reaping that can no longer block on such a process (R above), and a log relay that reports process states after 120 s of silence.
  - The rerun (`jobs/81632208-bca`) completed every step: 10 hidden tests at 200-258 s each, the train and visible evaluations, and `validate.py`. There was no stall and no reaping warning.
- **Headroom.** No method was found that beats the reference on `population_improvement`.
- **Scope.** LiveBench, Atari, Figure 1's population studies and 3-player Kuhn poker remain unscored.

## Reproducing this report

- `bash scripts/run.sh`: the reference end to end (paper artifacts, baseline, standard, train and hidden evaluation, `validate.py`), about 15 minutes.
- `python3 redteam/hardening_final/witness.py`: the public three-LP witness.
- `python3 redteam/hardening_final/run_bundle.py`: the 9 replays above, about 35 minutes, resumable.
- `python3 redteam/hardening_final/summarize.py`: the before/after comparison.
- Iteration 12's full replay of 65 shortcuts: `python3 redteam/replay_all.py`. It was not rerun against this test.
