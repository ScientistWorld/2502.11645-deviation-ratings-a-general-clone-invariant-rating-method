# Reproduction Milestones

**Current: core_claim**

## Progress Log

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

## Stop Justification
- Finalized at `core_claim`. The packaged environment is consistent, validated, and usable as a gym for the two scored experiments, but it does not include the paper's broader empirical sections, so a higher milestone would overclaim coverage.
