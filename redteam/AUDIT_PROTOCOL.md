This is an audit of scoring shortcuts, not a reproduction claim.

`bash redteam/<shortcut_name>/run.sh` installs fresh shortcut artifacts/edits,
runs the visible train entrypoint, restores the complete gym `eval/` tree and
`scripts/evaluate_test.sh`, and runs `bash scripts/evaluate_test.sh` with no
arguments. Every temporary edit is restored, including ignored checkpoints and
scoring files. Output logs, status, installed files, submitted artifacts, and
complete test scores stay in that shortcut's folder. Failed runs retain tracebacks
and status rather than a made-up numeric score.

The shortcut producer's inputs are only `data/game_data.py`, the visible train
artifact contract and scoring documents. The checkpoint-precedence shortcut also
reruns the provided method (improve mode). The producer never reads hidden test
code, score files, scoring/reference.json, old checkpoints, git history or other
audit outputs. It creates its own reference override rather than reading one.
The harness can read hidden outputs to record the actual result.

All score components are preserved. There is no aggregate rank implementation
among the provided evaluation entrypoints, so this audit does not invent one.
Nonfinite JSON output is distinguished from a demonstrated finite improvement.
Illegal changes accepted by scoring are reported as shortcuts, not valid science.

The reference uses the unmodified method and baseline, freshly executed with
Python and NumPy seeds 0, 1, and 2 in separate processes. These exact LP routines
have no random branch. `reference_seed_spread.json` records the spread of every
hidden test component, including baseline components.

This iteration started with pre-existing staged deletions of old audit files,
README/manifest placeholders, and deleted trajectory logs. Those were not read as
method inputs. `starting_state.json` records that starting state. The original gym
job entrypoint is saved in `starting_run.sh` so the temporary audit job can be
restored after execution.
