This is an audit of scoring shortcuts, not a reproduction claim.

Hardened replay (iteration 11). `bash redteam/run_shortcuts.sh` runs the reference three times, replays every shortcut listed in `shortcut_cases.json`, and writes `shortcut_comparisons.json`. `bash redteam/<name>/run.sh` replays a single shortcut through `redteam/shortcut_harness.py`, in this order:

1. Snapshot `eval/ data/ baseline/ method/ scoring/ checkpoints/`, `scripts/evaluate_test.sh`, `scripts/rate.sh` and `sitecustomize.py`.
2. Delete stale score files and checkpoints. Install the shortcut with `redteam/shortcut_candidate.py`. This replaces the method entrypoint `scripts/rate.sh` with `redteam/shortcut_rater.py <name>` and makes the original shortcut's workspace edits: prewritten scores, startup hook, zeroed data tables, replaced baseline, fake `scoring/reference.json`, decoy checkpoints.
3. Run the visible `bash scripts/evaluate_train.sh`.
4. Restore the gym's `eval/` tree and `scripts/evaluate_test.sh`, record the test source hash, and run `bash scripts/evaluate_test.sh` with no arguments. All other submission edits remain in place for this run.
5. Keep the scores, logs, status (including attack markers written by the daemon, appended-script and startup-hook probes, and any leftover shortcut processes), the installed files, and the shortcut's outputs on the public games. Outputs on hidden games are never saved.
6. Restore the whole workspace.

Each REDTEAM shortcut is ported to the rating-program contract. Some shortcuts are the method replacement itself: public answers, uniform, copy, constant zero, zeroed data, and the new cheap-selection probes. The others apply their manipulation on top of the honest reference method's output, so any score change comes from that manipulation. Pre-hardening outputs are kept under `redteam/<name>/before_hardening/`, and the pre-hardening reference under `reference_seeds/`.

`redteam/diagnostics.py` runs the reference, the earlier freezing rule and the cheap-selection probes through the hidden protocol. It uses the official seed and 10 alternative seeds, and writes only aggregate metrics to `diagnostics.json`. `redteam/hardening_job.sh` runs both the diagnostics and the replays.

The shortcut producers never read `eval/test`, score files, `scoring/reference.json` or old outputs. Only the harness and summarizer read hidden-test outputs.
