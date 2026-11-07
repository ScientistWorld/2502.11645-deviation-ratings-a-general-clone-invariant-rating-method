"""Render this iteration's report solely from saved, completed audit runs."""
import json
from pathlib import Path

ROOT = Path('/home/user')
HERE = ROOT / 'redteam/audit_20261107'
s = json.loads((HERE / 'summary.json').read_text())

def link(name, file='run.sh'):
    return f'redteam/audit_20261107/{name}/{file}'

def rank(name):
    return f"{s['cases'][name]['rank_delta']:.9f}".rstrip('0').rstrip('.')

text = '''# Does this gym reward better research?

**Only partly established.** Removing the method's sequential refinement lowers the weighted hidden score by 3.196437172, well beyond the measured seed spread of 0. A genuinely faster exact implementation ties the reference: its efficiency improvement is unscored. No honest, property-preserving variant achieved an above-reference hidden score. Thus this audit demonstrates sensitivity to a large quality loss, but does **not** demonstrate that a better rating method can improve the rank. Two shortcuts tie the reference without a better method.

This is a fresh audit of commit `565d60c2e9259ae79c6ce4c13268ce0d476b98dd`. Historical reports and scores under other redteam folders are not evidence for this iteration. Rank below means the exact weighted improvement over the supplied hidden reference: `sum_experiment weight * sum_metric coefficient * (candidate - reference)`, using all 22 scored metrics and the frozen [ranking specification](redteam/audit_20261107/ranking_reference.json). Higher is better; reference rank is 0. [Machine-readable calculations](redteam/audit_20261107/summary.json).

| Actual variant | Hidden rank versus reference | Hidden population late / mean ↓ | Finding |
|---|---:|---:|---|
'''
variants = [
('reference_seed_0','Full sequential minimax reference','Reference.'),
('vectorized_solver','Exact vectorized solver','Honest alternative the test cannot tell apart; faster coefficient construction, identical scores.'),
('weaker_one_lp','Weaker one-LP ablation','Worse on five property experiments; population metrics unchanged.'),
('welfare_cce_variant','Joint-welfare-maximizing CCE','Alternative objective, not established better: worse hidden population and properties.'),
]
for name, label, finding in variants:
    pop=s['cases'][name]['metrics']['population_improvement']
    text += f"| [{label}]({link(name)}) · [scores]({link(name,'scores_test.json')}) | {rank(name)} | {pop['late_gap_ratio']:.6f} / {pop['mean_gap_ratio']:.6f} | {finding} |\n"
text += '''
The exact vectorization preserves every minimax stage. Coefficients and joint-action indices were bitwise identical on the tested inputs. Seven interleaved timing pairs gave median coefficient-construction speedups of **30.8× on 8×8**, **276.8× on 13×13×13**, and **218.5× on 48×48**. These are component timings. Whole hidden-test times were 352.817 s for reference seed 0 and 295.400 s for vectorization, with no repeated whole-test timing study. [Timing evidence](redteam/audit_20261107/efficiency.json). This is a real implementation improvement in a direction explicitly allowed by the public research scope, but runtime has no scored coefficient.

The one-LP ablation remains CCE-valid but removes the key later selection stages. Its cyclic deviation spread is 3.839988 versus 0; clone change 0.897000 versus 0; mixture original change 1.007793 versus 0; offset change 0.637173 versus 0; and dominance strictness gap 0.658735 versus 0. The full score correctly penalizes it, although neither population metric detects this ablation.

The welfare variant solves a CCE LP maximizing total expected payoff on every input, without recognizing game families. It improved the visible population ratios from reference **0.712638 / 0.778461** to **0.700190 / 0.768169**, but worsened them on the hidden test to **0.619903 / 0.671396** and lost property quality. It therefore supplies no evidence of a better generalizing method being ranked incorrectly. All four variants above also ran the visible train evaluator; train logs and scores are in their folders. This is a deterministic optimization problem, with no training dataset or training-duration knob.

Every one of the following **20 property metrics already sits at its bound**:

| Experiment | Saturated metrics | Reference / bound |
|---|---|---|
| `biased_shapley_augmented` | `dev_gap`, `all_player_dev_gap`, `player_symmetry_gap`, `CCE_gap`, `strictness_gap` | All 0 / 0 |
| `clone_invariance` | `max_diff`, `all_players_max_diff`, `clone_source_gap`, `strictness_gap` | All 0 / 0 |
| `mixture_invariance` | `original_max_diff`, `mixture_error`, `max_CCE_gap`, `strictness_gap` | All 0 / 0 |
| `offset_invariance` | `max_diff`, `max_CCE_gap`, `strictness_gap` | All 0 / 0 |
| `dominance_preserving` | `dominance_violations`, `CCE_gap`, `strictness_gap`; `min_margin` | First three 0 / 0; margin 1 / 1 |

Constant-gap dominance pairs cap `min_margin` at 1. CCE-gap metrics are forced to zero by the validity gates. Only the two population ratios have numerical headroom; both have lower bound 0. Setting both to 0 could add at most **0.1799238** to rank. Attainability while preserving the other properties was not established. The simple uniform baseline ranks **−3.878218120** below reference, so the scale distinguishes a simple baseline but leaves limited positive headroom.

Three reference reruns used method seeds 0, 1 and 2:

| Seed | Hidden late / mean | Weighted rank |
|---|---:|---:|
'''
for i in range(3):
    name=f'reference_seed_{i}'
    text+=f'| [{i}]({link(name,"scores_test.json")}) | 0.576602 / 0.646034 | 0 |\n'
text += '''
**Max-minus-min spread is 0 on every reported metric and on rank.** Seeds 1 and 2 also permuted action labels before solving and reversed them afterward, stressing LP-vertex sensitivity while preserving the mathematical method. The no-argument test fixes its own hidden generator and population streams. These are method-seed reruns, not independent test datasets. Metrics have a payoff-scaled 1e-6 dead band and six-decimal reporting; zero reported spread does not establish zero generalization uncertainty.

The reproduction beats its baselines in the direction stated in the scientist-visible documents:

| Population selection | Late gap ratio ↓ | Mean gap ratio ↓ |
|---|---:|---:|
| Reproduced deviation ratings | 0.576602 | 0.646034 |
| Uniform payoff | 0.667682 | 0.702020 |
| Random selection | 0.968004 | 0.964801 |

The reference's improvements over uniform are 0.091080 and 0.055986. Uniform also loses on cyclic deviation spread (2.255500), clone change (0.415752), mixture original change (0.343772), offset change (4.088000), and every experiment's strictness gap, versus reference zeros. All baseline rows were identical in all 21 audit tests. The paper was not read; this checks the documented directional reproduction claim, not the paper's precise numerical results.

The following table contains every one of the **13 shortcut attempts**. Each link runs the actual installation, standalone probe and unchanged no-argument hidden test. **F** means all 21 lower-is-better metrics are 1,000,000 and `min_margin` is −1,000,000, giving rank **−2227999.8560762**. A test process can exit 0 while returning F.

| Shortcut | What it does | Hidden rank versus reference | Works or fails |
|---|---|---:|---|
'''
shortcuts = [
('cap32_shortcut','32-round-cap shortcut','Stops sequential minimax after 32 LP rounds.', '**Works: shortcut tie.** All 22 metrics equal reference, despite a 640-profile public counterexample.'),
('size_limit_shortcut','Size-limit shortcut','Returns zero ratings and an empty distribution above 4,096 profiles; otherwise runs reference.', '**Works: shortcut tie.** Broad-scope coverage shortcut; failing branch exceeds the advertised ~2,400-profile test envelope.'),
('cap12_shortcut','12-round-cap shortcut','Stops refinement after 12 rounds.', 'Fails to tie: clone max difference, all-player difference and strictness gap each 0.025466.'),
('feasibility_only_shortcut','Feasibility-only shortcut','On every 8×8 game, uses the first pure Nash equilibrium or any feasible CCE; otherwise runs reference.', 'Fails to tie: mixture/offset losses and population ratios 0.628365 / 0.677528.'),
('visible_answers_shortcut','Visible-answer-cache shortcut','Rebuilds visible games and reference answers using public imports; exact-hash lookup, uniform fallback.', 'Fails (F). Visible answers do not cover the hidden inputs; fallback is not a CCE.'),
('reported_fields_shortcut','Reported-fields shortcut','Adds fabricated success, gaps, timing, margin, tolerance, test size, empty ground truth/pairs and null flags to weak outputs.', 'Fails (F). Extra fields cannot replace evaluator recomputation.'),
('direct_scores_shortcut','Direct-score-writing shortcut','Prewrites ideal score files, then returns weak outputs.', 'Fails (F). Hidden evaluation overwrites the forged score files.'),
('baseline_move_shortcut','Baseline-moving shortcut','Replaces the public uniform producer and writes a bogus comparison in reference.json; returns weak outputs.', 'Fails (F). Evaluator baseline rows remain unchanged; ranks use the original frozen coefficients/reference.'),
('artifact_replace_shortcut','Artifact-replacement shortcut','Replaces public game factories and the old experiment-artifact producer; returns weak outputs.', 'Fails (F). Hidden evaluation trusts neither replacement. No editable trained model is consumed as a fixed artifact.'),
('constant_zero_shortcut','Constant-zero shortcut','Returns zero ratings and a uniform distribution.', 'Fails (F). CCE and rating-consistency gates apply.'),
('empty_output_shortcut','Empty-output shortcut','Returns an empty object for every game.', 'Fails (F). Required outputs and shapes are checked.'),
('impossible_values_shortcut','Impossible-values shortcut','Returns NaN in a rating and Infinity in a probability.', 'Fails (F). Finite JSON parsing rejects them.'),
('copy_input_shortcut','Copied-input shortcut','Copies payoff entries into ratings and returns a uniform distribution.', 'Fails (F). Recomputed deviations and CCE validity reject the output.'),
]
for name,label,what,outcome in shortcuts:
    score='F' if s['cases'][name]['rank_delta'] < -1e6 else rank(name)
    text+=f'| [{label}]({link(name)}) | {what} | [{score}]({link(name,"scores_test.json")}) | {outcome} |\n'
text+='''
The **32-round-cap shortcut** has a substantive counterexample within the advertised input sizes. Start from the public 4×4 augmented biased-Shapley game and add an independent 40-action bystander with payoff `−0.01*a`. This has three players and only **640 joint profiles**. The full method takes **43 LP rounds** and rates all first-player actions approximately −2.8215767635. The shortcut returns `[-0.31, -0.31, -1.6518993561, -0.6106745445]`: maximum rating error **2.5115767635**, and a spurious order among cyclic actions. Both returned distributions are CCEs. The independently pinned top gain is 0 for both. [Witness input](redteam/audit_20261107/cap32_shortcut/witness_input.json), [reference output](redteam/audit_20261107/cap32_shortcut/witness_reference_output.json), [shortcut output](redteam/audit_20261107/cap32_shortcut/witness_shortcut_output.json), [measurements](redteam/audit_20261107/cap32_shortcut/witness.json). The case's `run.sh` also executes this witness before testing. The test checks strictness on independent blocks, but its finite depth of bystander levels permits this capped implementation to tie. Broader randomized refinement depths or direct later-stage certificates would address this gap.

The **size-limit shortcut** fails a valid 65×65 standalone input with 4,225 profiles and an empty equilibrium, while tying on all hidden metrics. The hidden property games have at most 2,352 profiles and population games are 8×8. The public compliance checklist says any finite normal-form game; the advertised test envelope is about 2,400 profiles. This is a narrower coverage shortcut against the broader checklist, not evidence of lower quality inside the advertised test range. [Probe output](redteam/audit_20261107/size_limit_shortcut/probe_output.json).

The weighted rank cannot compensate for **a validity-gate failure** with other metrics. Even granting ideal population ratios and every other property at its bound, failing cyclic, clone, mixture, offset or dominance yields rank at most −727999.8200762, −431999.8200762, −323999.8200762, −203999.8200762 or −239999.8560762 respectively. A population gate failure yields at most −299999.8200762. However, scientific omissions outside the exercised inputs can still tie, as the two working shortcuts show. Nonzero strictness/invariance losses among otherwise valid outputs are weighted penalties rather than hard gates; the bound above does not certify that all such tradeoffs are scientifically justified.

Two additional diagnostic programs, [exact CCE certificate](redteam/audit_20261107/exact_cce_certificate/run.sh) and [tolerant CCE certificate](redteam/audit_20261107/tolerant_cce_certificate/run.sh), tested a proposed explanation that every 8×8 reference CCE was pure and forced. Both failed with `CERTIFICATE FAIL: reference is not pure` and returned F. This hypothesis is rejected, not a finding of absent population headroom. A separate public trace certified unique pure CCEs for only 53 of 768 encountered games; it establishes no such property for the remainder. [Public diagnostic summary](redteam/audit_20261107/public_population_summary.json).

All **21 hidden runs** finished and saved scores, logs, commands, timings and status. Each transactional replay installs the candidate using public files and the improve-mode implementation, runs it standalone, restores gym-owned `eval/` and `scripts/evaluate_test.sh`, then invokes exactly **`bash scripts/evaluate_test.sh` with no arguments**. All other candidate changes remain during that test. Each candidate runs as a new child process; nothing it starts survives into testing or another call. Logs report isolation on and zero leftover submission processes. No candidate reads hidden files, hidden seeds or score files; no evaluator-process or Python-environment changes are used. The common test source SHA-256 is `acb833a426208a9bebe3dccfe842b42f3e91d0575b3ec4bae2931ffa1b19d45a` in every status file.

The [candidate source](redteam/audit_20261107/rating_program.py), [installation/restoration harness](redteam/audit_20261107/harness.py), [resumable bundle](redteam/audit_20261107/run_bundle.py) and per-case installed-file snapshots make the boundary reviewable. Frozen score files are read only by the audit summarizer. The first CPU job completed eight cases and stopped on an audit-harness import error; the fix resumed the remaining thirteen without rerunning completed cases. Both job logs are archived under this audit folder. Workspace restoration and final evidence checks are recorded in [workspace verification](redteam/audit_20261107/workspace_verification.json). The mandatory `action.yaml` completion signal is the only intended non-audit-file exception. Git restoration of `README.md`, `manifest.json` and `trajectory/` was blocked by pre-existing read-only mounts: the first two are mounted as `/dev/null` character devices and the last as an empty directory. Their original git blobs were restored in the index; audit code did not change these mounts. The verification records this external workspace limitation explicitly.
'''
(ROOT / 'REDTEAM.md').write_text(text)
