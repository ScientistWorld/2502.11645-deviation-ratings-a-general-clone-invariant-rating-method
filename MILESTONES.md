# Reproduction Milestones

**Current: method_runs**

## Progress Log

### [2026-04-05] - method_runs
- Implemented deviation rating algorithm (Algorithm 1) in method/deviation_rating.py
- Fixed game construction: biased Shapley game is 3×3 (R,P,S only — the cycle game)
- All experiments implemented: Shapley game, clone invariance, Livebench LLM rating, population study
- Fixed scores.json format to only include numeric metrics matching reference.json
- SCS solver with improved convergence parameters
- Previous test: algorithm runs, Livebench works (top4_overlap=4/4), but Shapley game needs CCE_gap=0

### [2026-04-04] - none
- Initial workspace setup
- Read the paper thoroughly
