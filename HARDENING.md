# Hardening report (iteration 12, final)

`REDTEAM.md` replayed 62 shortcuts through the hidden test. Five paid: they tied the reference's perfect score without doing the paper's work.
- **zero_gain_fallback** and **lax_cce** select a non-strict equilibrium that is still invariant; equilibrium selection was unmeasured.
- **batch_transport** made invariant-looking pairs by copying one game's answer to its transformed copy in the same batch.
- **large_game_abandonment** returned nothing for games above 1,024 joint actions; there were none in the test.
- **prestarted_writer** rewrote the score file after the test exited.

The REDTEAM also noted that the reference sat at the bound of every scored metric, so the test could only measure reproduction.

This iteration:
- closes all five;
- adds a scored headroom experiment from the paper (Section 5.3, population improvement in Sheriff);
- fixes the reference implementation where the new games exposed accumulated LP round-off;
- reruns the reference and all 65 shortcuts (the 62 plus 3 new probes aimed at the new defences) through the final hidden test.

After hardening:
- **No shortcut beats the reference, and none ties it without running the paper's method underneath.**
- 49 are scored as failed in every experiment they touch.
- 9 score worse.
- 7 tie. Each of these runs the reference method and adds a manipulation that the test ignores or that has no effect.

## What changed

| ID | Fix | Where |
|---|---|---|
| S | **`strictness_gap` in every property experiment.** For each game the evaluator computes the smallest largest deviation gain any CCE attains (the matrix-game value `min_s max_(p,a') delta`). It solves an LP in pure Python and certifies the result with the dual bound (gap at most 1e-9 of scale, else no score). It then scores the submitted equilibrium's excess over it. On the biased Shapley games that minimum is -680/241 (paper Table 2). A CCE with every gain 0, the least strict CCE, any feasible CCE and the first pure Nash equilibrium all score 2.8-6.7 on the cyclic family (hidden and 4 alternative suites) and about 0.7 on the other families; the reference scores 0. | `strictest_epsilon`, `strictness_gap` |
| P | **One call per population iteration, invariance pairs split across calls.** The rating program is called 96 times. Each call carries 8 population meta-games and a share of the about 210 property games, shuffled and anonymised. The two games of every invariance pair are always in different calls, so they cannot be made consistent by transporting an answer inside a batch. | `schedule_property_games`, `evaluate_hidden` |
| T | **Stateless calls.** Inside the job container, a call that creates, changes or deletes any file outside its temporary directory fails every game it carried. Watched: the workspace, `/tmp`, `/var/tmp`, `/dev/shm`. Not watched: system-managed paths, listed under "could not fix". This stops cross-call memory (probe `memo_transport`) and the appended-script and startup-hook probes from even running their payload. | `_file_state`, `run_rater` |
| K | **Process sweep at the start of the test.** Inside the job container's private PID namespace (PID 1 owned by this user), the hidden test kills every process of the job except its ancestors and readers of their output pipes. A watcher started before the test (`prestarted_writer`) is gone before any score exists. | `terminate_foreign_processes` |
| L | **Large games.** Every family now contains games above 1,000 joint actions. Clone/mixture/offset/dominance families use 3-player games of 1,089-1,210 joint actions; the cyclic family has a symmetric population with 33 strategies per player. | `LARGE_DIMS`, `_shapley_family` |
| M | **Sheriff meta-games among the property games.** The clone, mixture, offset and dominance families include meta-games of random Sheriff populations, drawn exactly like the population experiment's. A program that treats "population-like" games differently is exposed by the invariance checks (probe `sheriff_special_case`). | `_SheriffSource` |
| H | **Headroom experiment `population_improvement` (paper Section 5.3).** Sheriff with the paper's parameters. 8 runs x 96 iterations of "rate, drop each player's bottom quarter, add new random policies". Progress is the full-game CCE gap under the meta-game's maximum-entropy CCE. The evaluator fixes the game, the candidate streams, the tie-breaking and the gap measure. Weight 0.2; the other five weights are scaled by 0.8 with their ratios unchanged. | `PopulationLoop`, `scoring/reference.json` |
| V | **Visible side mirrors the test.** `eval/protocol.py` (train and standard evaluation) runs the same protocol, gates and experiments on the five public games, plus families and a population run from the visible `TRAIN_SEED`. It shares no code with `eval/test/`. | `eval/protocol.py` |
| N | **Reference numerics (method code).** On some new games HiGHS reported the sequential LP infeasible after accumulated round-off: Sheriff meta-games (job 1: population failed) and about 1,000-action mixture games. Coefficients are now scaled by the payoff scale. Only when an LP is reported infeasible is it re-solved: first with frozen gains in bands of relative half-width 1e-9 to 1e-7, then re-centred on the previous distribution. Each attempt has a 60 s limit. Ratings are returned as the gains of the returned distribution. The selection rule is unchanged (paper Section 4.1 and Appendix B). On the hidden population run the fallback was used 0 times. | `method/deviation_rating.py` |

Iteration-11 defences stay in force: strict parsing and validity gates, everything recomputed, comparisons fixed by `eval/`, `python3 -I` and `exec`, the per-call subreaper, and bystander players.

Hidden test SHA-256 (final): `68494d8f5e58b931234c1ddf9d70a5cad3fc1a5eb7ff1f919292a1a87a200bf9`. Before this iteration: `3b55cfa0…685eb7`.

### Replay protocol

`python3 redteam/replay_all.py` replays every case through its own harness (iteration 11's `redteam/shortcut_harness.py` or the redteam's `redteam/audit_v2/shortcut_harness.py`). Each replay installs the shortcut, restores the gym's `eval/` and `scripts/evaluate_test.sh`, runs `bash scripts/evaluate_test.sh` with no arguments, keeps the scores, log and status in `redteam/<name>/final/`, and restores the workspace. The train slice was not run in these replays because no hidden score depends on it. `python3 redteam/summarize_final.py` writes the comparison (`redteam/final_comparisons.json`).

59 shortcuts were replayed against an intermediate hidden test, `ddfb1cf4…6c1c6546`. It differed from the final one only in two lines: the final test also leaves `.git-shims/` and `.git-credentials` unwatched. The job system rewrites them when it commits job progress, and in four replays that rewrite had failed calls. The two versions behave identically unless one of those files changes during a call. None of the 59 logs shows such a change (all their stateless-call failures name the shortcut's own files), so their results are those of the final test. The four affected shortcuts and both reference runs were replayed against the final test.

## Every shortcut, before and after

"Before" is the hidden-test score in `REDTEAM.md` (R = tied the reference exactly, F = failure vector, "below R" = worse tuple). "After" is the final hidden test (`redteam/<name>/final/scores_test.json`):
- **F (all 6):** every experiment is scored as failed.
- **Failed in X:** those experiments are scored as failed and the rest tie R.
- **Worse in X:** finite scores below the reference there.

The population experiment counts as an experiment. A row whose population entry ties R ran the reference's selection on the population games. "Gates (iteration 11)" means the shortcut was already caught by iteration 11's gates, which remain in force.

| Shortcut | Before (REDTEAM.md test score) | Fix | After (final hidden test) |
|---|---|---|---|
| [public_answers_shortcut](redteam/public_answers_shortcut/final/scores_test.json) | F | gates (iteration 11) | F (all 6) |
| [uniform_payoffs_shortcut](redteam/uniform_payoffs_shortcut/final/scores_test.json) | F | gates (iteration 11) | F (all 6) |
| [constant_zero_shortcut](redteam/constant_zero_shortcut/final/scores_test.json) | F | gates (iteration 11) | F (all 6) |
| [copy_input_shortcut](redteam/copy_input_shortcut/final/scores_test.json) | F | gates (iteration 11) | F (all 6) |
| [empty_artifacts_shortcut](redteam/empty_artifacts_shortcut/final/scores_test.json) | F | gates (iteration 11) | F (all 6) |
| [direct_scores_shortcut](redteam/direct_scores_shortcut/final/scores_test.json) | F | gates (iteration 11) | F (all 6) |
| [reported_fields_shortcut](redteam/reported_fields_shortcut/final/scores_test.json) | F | gates (iteration 11) | F (all 6) |
| [null_ratings_shortcut](redteam/null_ratings_shortcut/final/scores_test.json) | F | gates (iteration 11) | F (all 6) |
| [nan_ratings_shortcut](redteam/nan_ratings_shortcut/final/scores_test.json) | F | gates (iteration 11) | F (all 6) |
| [nan_equilibrium_shortcut](redteam/nan_equilibrium_shortcut/final/scores_test.json) | F | gates (iteration 11) | F (all 6) |
| [infinite_equilibrium_shortcut](redteam/infinite_equilibrium_shortcut/final/scores_test.json) | F | gates (iteration 11) | F (all 6) |
| [overflow_equilibrium_shortcut](redteam/overflow_equilibrium_shortcut/final/scores_test.json) | F | gates (iteration 11) | F (all 6) |
| [negative_equilibrium_shortcut](redteam/negative_equilibrium_shortcut/final/scores_test.json) | F | gates (iteration 11) | F (all 6) |
| [scaled_equilibrium_shortcut](redteam/scaled_equilibrium_shortcut/final/scores_test.json) | F | gates (iteration 11) | F (all 6) |
| [zero_equilibrium_shortcut](redteam/zero_equilibrium_shortcut/final/scores_test.json) | F | gates (iteration 11) | F (all 6) |
| [short_equilibrium_shortcut](redteam/short_equilibrium_shortcut/final/scores_test.json) | F | gates (iteration 11) | F (all 6) |
| [rating_inflation_shortcut](redteam/rating_inflation_shortcut/final/scores_test.json) | F | gates (iteration 11) | F (all 6) |
| [unbounded_margin_shortcut](redteam/unbounded_margin_shortcut/final/scores_test.json) | F | gates (iteration 11) | F (all 6) |
| [infinite_margin_shortcut](redteam/infinite_margin_shortcut/final/scores_test.json) | F | gates (iteration 11) | F (all 6) |
| [string_infinity_shortcut](redteam/string_infinity_shortcut/final/scores_test.json) | F | gates (iteration 11) | F (all 6) |
| [boolean_ratings_shortcut](redteam/boolean_ratings_shortcut/final/scores_test.json) | F | gates (iteration 11) | F (all 6) |
| [offset_translation_shortcut](redteam/offset_translation_shortcut/final/scores_test.json) | F | gates (iteration 11) | F (all 6) |
| [mixture_original_drift_shortcut](redteam/mixture_original_drift_shortcut/final/scores_test.json) | below R | gates (iteration 11) | failed in shapley, clone, mixture; ties elsewhere |
| [clone_no_equilibrium_shortcut](redteam/clone_no_equilibrium_shortcut/final/scores_test.json) | below R | gates (iteration 11) | failed in shapley, clone; ties elsewhere |
| [clone_arbitrary_ratings_shortcut](redteam/clone_arbitrary_ratings_shortcut/final/scores_test.json) | below R | gates (iteration 11) | failed in shapley, clone; ties elsewhere |
| [short_action_set_shortcut](redteam/short_action_set_shortcut/final/scores_test.json) | F | gates (iteration 11) | F (all 6) |
| [empty_action_set_shortcut](redteam/empty_action_set_shortcut/final/scores_test.json) | F | gates (iteration 11) | F (all 6) |
| [missing_player_shortcut](redteam/missing_player_shortcut/final/scores_test.json) | F | gates (iteration 11) | F (all 6) |
| [reverse_dominance_pairs_shortcut](redteam/reverse_dominance_pairs_shortcut/final/scores_test.json) | F | gates (iteration 11) | F (all 6) |
| [single_dominance_pair_shortcut](redteam/single_dominance_pair_shortcut/final/scores_test.json) | F | gates (iteration 11) | F (all 6) |
| [empty_dominance_pairs_shortcut](redteam/empty_dominance_pairs_shortcut/final/scores_test.json) | R (ties) | gates (iteration 11) | ties the reference |
| [phantom_dominance_action_shortcut](redteam/phantom_dominance_action_shortcut/final/scores_test.json) | F | gates (iteration 11) | F (all 6) |
| [zero_mixture_weights_shortcut](redteam/zero_mixture_weights_shortcut/final/scores_test.json) | below R | gates (iteration 11) | failed in shapley, clone, mixture; ties elsewhere |
| [onehot_mixture_shortcut](redteam/onehot_mixture_shortcut/final/scores_test.json) | below R | gates (iteration 11) | failed in shapley, clone, mixture; ties elsewhere |
| [extrapolated_mixture_shortcut](redteam/extrapolated_mixture_shortcut/final/scores_test.json) | below R | gates (iteration 11) | failed in shapley, clone, mixture; ties elsewhere |
| [rounding_shortcut](redteam/rounding_shortcut/final/scores_test.json) | R (ties) | gates (iteration 11) | ties the reference |
| [baseline_replace_shortcut](redteam/baseline_replace_shortcut/final/scores_test.json) | F | gates (iteration 11) | F (all 6) |
| [data_replace_shortcut](redteam/data_replace_shortcut/final/scores_test.json) | F | gates (iteration 11) | F (all 6) |
| [reference_override_shortcut](redteam/reference_override_shortcut/final/scores_test.json) | F | gates (iteration 11) | F (all 6) |
| [python_startup_shortcut](redteam/python_startup_shortcut/final/scores_test.json) | F | python3 -I, T | F (all 6) |
| [checkpoint_precedence_shortcut](redteam/checkpoint_precedence_shortcut/final/scores_test.json) | R (ties) | gates (iteration 11) | ties the reference |
| [method_id_collision_shortcut](redteam/method_id_collision_shortcut/final/scores_test.json) | R (ties) | gates (iteration 11) | ties the reference |
| [global_rating_scale_shortcut](redteam/global_rating_scale_shortcut/final/scores_test.json) | F | gates (iteration 11) | F (all 6) |
| [masked_nan_ratings_shortcut](redteam/masked_nan_ratings_shortcut/final/scores_test.json) | F | gates (iteration 11) | F (all 6) |
| [masked_nan_strings_shortcut](redteam/masked_nan_strings_shortcut/final/scores_test.json) | F | gates (iteration 11) | F (all 6) |
| [single_lp_shortcut](redteam/single_lp_shortcut/final/scores_test.json) | below R | bystanders (iteration 11) | worse in shapley, clone, mixture, offset; ties elsewhere |
| [feasibility_cce_shortcut](redteam/feasibility_cce_shortcut/final/scores_test.json) | below R | S | worse in shapley, clone, mixture, offset, dominance, population |
| [pure_nash_shortcut](redteam/pure_nash_shortcut/final/scores_test.json) | below R | S | worse in shapley, clone, mixture, offset, dominance, population |
| [uniform_gains_shortcut](redteam/uniform_gains_shortcut/final/scores_test.json) | F | gates (iteration 11) | F (all 6) |
| [detached_rewriter_shortcut](redteam/detached_rewriter_shortcut/final/scores_test.json) | R (ties) | subreaper kill | ties the reference |
| [script_append_shortcut](redteam/script_append_shortcut/final/scores_test.json) | R (ties) | T + exec | F (all 6) |
| [zero_gain_fallback_shortcut](redteam/zero_gain_fallback_shortcut/final/scores_test.json) | R (ties) | S (strictness_gap) | worse in shapley, clone, mixture, offset; ties elsewhere |
| [lax_cce_shortcut](redteam/lax_cce_shortcut/final/scores_test.json) | R (ties) | S | worse in shapley, clone, mixture, offset, dominance, population |
| [zero_nondominated_shortcut](redteam/zero_nondominated_shortcut/final/scores_test.json) | below R | S | worse in shapley, clone, mixture, offset, dominance, population |
| [batch_transport_shortcut](redteam/batch_transport_shortcut/final/scores_test.json) | R (ties) | S, P (pairs split across calls) | worse in shapley, clone, mixture, offset, dominance, population |
| [large_game_abandonment_shortcut](redteam/large_game_abandonment_shortcut/final/scores_test.json) | R (ties) | L (games above 1,000 joint actions) | failed in shapley, clone, mixture, offset, dominance; ties elsewhere |
| [negative_tolerance_shortcut](redteam/negative_tolerance_shortcut/final/scores_test.json) | R (ties) | gates (iteration 11) | ties the reference |
| [tiny_rating_mismatch_shortcut](redteam/tiny_rating_mismatch_shortcut/final/scores_test.json) | R (ties) | gates (iteration 11) | ties the reference |
| [bystander_drop_shortcut](redteam/bystander_drop_shortcut/final/scores_test.json) | F | gates (iteration 11) | failed in shapley, clone, mixture, offset, dominance; ties elsewhere |
| [fixed_options_shortcut](redteam/fixed_options_shortcut/final/scores_test.json) | F | gates (iteration 11) | F (all 6) |
| [score_symlink_shortcut](redteam/score_symlink_shortcut/final/scores_test.json) | F | gates (iteration 11) | F (all 6) |
| [prestarted_writer_shortcut](redteam/prestarted_writer_shortcut/final/scores_test.json) | R (ties) | K (process sweep) | F (all 6) |
| [strict_batch_transport_shortcut](redteam/strict_batch_transport_shortcut/final/scores_test.json) | new probe | P | worse in shapley, clone, mixture, offset; ties elsewhere |
| [memo_transport_shortcut](redteam/memo_transport_shortcut/final/scores_test.json) | new probe | T (stateless calls) | F (all 6) |
| [sheriff_special_case_shortcut](redteam/sheriff_special_case_shortcut/final/scores_test.json) | new probe | M (Sheriff meta-games among property games) | worse in mixture, offset, population; ties elsewhere |

What the seven ties are:
- `empty_dominance_pairs`, `checkpoint_precedence` and `method_id_collision` add advisory fields or decoy files that the test never reads.
- `rounding` and `tiny_rating_mismatch` add rating noise below the 1e-6 tolerance.
- `negative_tolerance` replaces zero probabilities by -5e-7, within the tolerance and clipped.
- `detached_rewriter` spawns a daemon that the per-call subreaper kills; no rewrite marker was written.

All seven run the reference underneath and gain nothing.

The five shortcuts that paid before, in detail:
- **zero_gain_fallback, lax_cce:**
  - Strictness: `strictness_gap` 2.82 on the cyclic family and 0.68-0.73 on the other families. Their invariance metrics still tie, so strictness is what catches them.
  - Population: lax scores 0.637 against the reference's 0.577 (worse). zero_gain_fallback's population score equals the reference's: on those games its selection either falls back to the reference or makes the same drops.
  - Alternative suites: the pure zero-gain selection also breaks clone invariance (`max_diff` up to 0.98).
- **batch_transport:** pairs never share a call, so it loses invariance (clone 0.64, mixture drift 0.66, offset 0.05) on top of strictness.
- **large_game_abandonment:** fails every property experiment, because each contains games above 1,024 joint actions.
- **prestarted_writer:** the sweep stopped it before testing ("stopped 1 leftover process"). No rewrite marker, the log and persisted scores agree, and the weak outputs fail.

The new probes:
- `strict_batch_transport`: transport with a first-LP base, strict at the top level. Pairs are split, so its invariance is that of a single LP: Shapley `dev_gap` 1.36, mixture drift 0.84.
- `memo_transport`: the same with cross-call memory in `~/.cache`. It fails every call that writes the memo.
- `sheriff_special_case`: the least strict CCE on 8x8 games, the reference elsewhere. Worse on the population experiment (0.637). Caught on the Sheriff property games: mixture drift 0.245, `strictness_gap` 0.007 in mixture and offset.

## Reference score, before and after

Before is the REDTEAM's fresh unmodified reference on the previous hidden test. After is the final hidden test, rerun from the final code: `scoring/scores_test.json`, byte-identical in 3 runs (`redteam/reference_runs/run_{0,1}/final/`, `redteam/job6/test.log`).

| Experiment | Reference before | Reference after | Uniform baseline after |
|---|---|---|---|
| biased_shapley_augmented | dev/all/symmetry/CCE gaps 0 | dev/all/symmetry/CCE gaps 0, strictness_gap 0 | 2.934636 / 5.122333 / 3.832333 / 3.209813, strictness 4.286515 |
| clone_invariance | 0 / 0 / 0 | 0 / 0 / 0, strictness 0 | 0.25075 / 0.25075 / 0, strictness 3.857303 |
| mixture_invariance | 0 / 0 / 0 | 0 / 0 / 0, strictness 0 | 0.407582 / 0 / 3.086416, strictness 2.621413 |
| offset_invariance | 0 / 0 | 0 / 0, strictness 0 | 3.84 / 1.738788, strictness 1.451191 |
| dominance_preserving | 0 violations, margin 1, CCE 0 | 0, 1, 0, strictness 0 | 0 / 1 / 2.507909, strictness 2.104818 (zero rating: 65 violations; negative uniform: 65, margin -97.33) |
| population_improvement (new) | — | late 0.576602, mean 0.646034 | 0.667682 / 0.70202; random selection 0.968004 / 0.964801 |

The property values of the reference are unchanged; the property games, the baselines' values and the new metric are different because the test is.

The visible side was regenerated from the reference run (`scoring/scores.json`, `scoring/scores_train.json`):
- **Property experiments:** the reference scores 0 on every metric.
- **Population (train seed):** reference late gap ratio 0.712638, uniform 0.797493, random 1.083548.

## Headroom check

- **The reference sits at the bound of every property metric:** every gap 0, `strictness_gap` 0, `dominance_violations` 0 and `min_margin` 1 (the maximum for any deviation-gain rating). This held on the hidden suite and on 4 alternative suites (`redteam/property_diagnostics.json`). No method can score higher there.
- **Added: `population_improvement`, weight 0.2**, from where the paper's own method is measured empirically and is imperfect (Section 5.3, Figure 3b).
  - The reference's late gap ratio is 0.577 on the hidden test; the bound is 0.
  - Uniform averaging: 0.668. Random selection: 0.968.
  - Other selections score differently, so the metric is not stuck: the least strict CCE 0.637; any feasible CCE, the first pure Nash equilibrium and batch transport 0.624.
  - No method we tried beats the reference, so the headroom is untested.
- **Paper's numbers.** In `scoring/reference.json`, read off Figure 3b (one run, 512 iterations) at the gym's 96-iteration horizon: late gap ratio 0.649 for deviation rating and 0.821 for uniform. The paper ran 8 policies per player like the gym, but 512 iterations and one run; the gym uses 8 runs x 96 iterations.
- **Horizon choice.** 96 iterations was chosen from 6 non-hidden seeds x 256 iterations (`redteam/population_diagnostics.json`): the reference beats uniform on every seed from 96 iterations on. It also keeps one evaluation to about 3.5 minutes; each call costs about 1.6 s of program start-up.

## Larger than seed noise

- **Reference runs.** The reference is deterministic, and its three hidden-test runs are byte-identical.
- **Population effect** (`redteam/population_diagnostics.json`, 6 non-hidden seeds x 8 runs, 96 iterations, same candidate streams for every method):

  | Method | Late gap ratio, mean of 6 seeds | Per seed |
  |---|---|---|
  | Reference | 0.649 | 0.570-0.767 |
  | Uniform | 0.716 | — |
  | Random | 1.062 | — |

  The paired advantage over uniform is positive on 6/6 seeds: 0.041-0.107 (late) and 0.038-0.064 (mean). On the hidden seed it is 0.091 (late). The variation between seeds is larger than the effect, but every method sees the same draws, so the comparison that matters is paired.
- **Property metrics.** These are exact: 0 for the reference on every suite. The cheap selections fail every suite:
  - **lax:** `strictness_gap` 2.8-6.7 on the cyclic family.
  - **single LP:** Shapley `dev_gap` 1.4-3.7.
  - **zero-gain:** strictness 2.8-6.7, plus clone drift 0.22-0.98.

## Direction of the paper's claims

- **Property claims:** the reference beats the uniform baseline on cyclic equality, clone, mixture and offset invariance, CCE feasibility and strictness, and ties it on dominance (both preserve it).
- **Section 5.3 claim** ("deviation ratings drive a reduction in the gap in a general-sum game"): reproduced in direction on the hidden test, the train seed and all 6 diagnostic seeds.

The effect is smaller than in the paper. In this implementation uniform averaging also lowers the gap to about 0.67-0.72 of its start, where the paper's uniform run stays near 0.85. Possible causes:
- the paper's footnote 6, the distribution used to measure the population's gap, is not in the text; the gym uses the maximum-entropy CCE;
- details of random-policy sampling;
- the paper reports one run.

## Reference implementation fix (N)

The numerics change in `method/deviation_rating.py` was needed because the new games broke the previous implementation. In job 1 it raised "LP infeasible" on some hidden Sheriff meta-games and on large mixture games, so honest calls failed.

The algorithm is unchanged:
- the same sequential LP and the same nonzero-dual freezing;
- the same results on every game where the old code succeeded: identical property scores, and population trajectories identical to the pre-fix diagnostics;
- the fallback attempts run only when HiGHS reports infeasibility.

Paper Table 2 (all four ratings -2720/964) is still reproduced by `scripts/method.sh`.

## What I could not fix, stated plainly

- **Strictness is scored only at the top level.** Below it, a different selection (for example lexicographically least strict among the strictest-at-the-top CCEs) is not measured directly.
  - Such a selection is caught when it breaks an invariance.
  - It is not caught when it is itself invariant. On the Sheriff meta-games the top-level minimum is 0, so strictness says nothing there.
  - Scoring the full lexicographic order needs the same chain of degenerate LPs as the method itself. In floating point those LPs are ill-posed: a 1e-16 violation moved one optimum by 4.7. A float ground truth could penalise a correct method.
- **The stateless check has blind spots.**
  - **Unwatched paths:** `.git`, `.git-shims`, `.git-credentials`, `jobs/`, `logs/`, `trajectory/`, `.claude*`, `.codex`, `shared/`, the container image files, and modifications of files above 256 MB.
  - **Why they are unwatched:** the job system writes some of them while a job runs. Two false positives in this iteration (the overlay image, the git shims) failed honest calls before they were excluded.
  - **Residual risk:** a program that hides cross-call state in one of these paths would not be caught. It would also have to detect which games are pairs, and its gain is bounded: it can only tie the strict reference on the property experiments.
- **Isolation only inside the job container.** The process sweep and the stateless check are active only in a private PID namespace (PID 1 owned by the user), as in the system's jobs. Run on a shared host, they are off and the test reverts to iteration-11 isolation.
- **Unsandboxed rater.** The rating program can still read `eval/test/evaluate.py`, including the seed, while it runs. Closing this needs OS-level sandboxing that this environment does not provide.
- **Container trust.** The container is trusted as before: a modified interpreter or standard library in an agent-built image is outside the evaluator's reach.
- **Untested headroom.** No tried method beats the reference on `population_improvement`, so whether this experiment has headroom has not been shown. The metric is far from its bound and does separate methods.
- **Population effect size.** The reference's lead over uniform (about 0.07 late gap ratio) is real on every seed but smaller than in the paper (see above).
- **Unexplained stall.** Job 3's hidden test stalled for 18 minutes and the job was killed by the infrastructure ("Ray actor no longer exists"). The cause was not identified. Afterwards:
  - every LP got a time limit and every call a 300 s limit;
  - the evaluator prints progress;
  - the same hidden-seed population loop, run in-process, took 28 s with no stall.

  Four later hidden-test runs completed in 198-215 s.
- **Train-phase isolation.** Train runs were skipped in the replays, so the train-phase behaviour of shortcuts is not re-recorded. The train evaluator has the same gates and stateless check but no process sweep.
- **Scope.** LiveBench, Atari, Figure 1's population studies and 3-player Kuhn poker are not scored.

## Reproducing this report

- `bash scripts/run.sh`: the reference end to end (paper artifacts, baseline, standard/train/hidden evaluation, `validate.py`), about 15 minutes.
- `python3 redteam/replay_all.py`: the reference twice and all 65 shortcuts through the hidden test, about two hours, resumable across jobs. Then `python3 redteam/summarize_final.py`.
- **Diagnostics:**
  - `python3 redteam/property_diagnostics.py` (hidden plus 4 seeds, in-process);
  - `python3 redteam/population_diagnostics.py --iterations 256` (6 seeds);
  - `python3 redteam/hidden_population_check.py` (the hidden population loop, in-process).
- **Job logs:** `redteam/job1`-`job6`.
