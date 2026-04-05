# Reproduction Milestones

**Current: method_runs**

## Progress Log

### [2026-04-05] - method_runs
- Algorithm runs end-to-end with scipy.optimize.linprog
- Livebench works (top4_overlap=4/4) — 3-player game converges correctly
- Population study works (dev spread=0) — symmetric games solve correctly
- Previous issue: biased Shapley game (3x3) didn't converge to CCE_gap=0 with ECOS
- Fix: replaced CVXPY/ECOS with scipy.optimize.linprog for more reliable LP solving
- The strictest CCE of the biased Shapley game should be a pure NE → CCE_gap=0

### [2026-04-04] - none
- Initial workspace setup, read the paper thoroughly
