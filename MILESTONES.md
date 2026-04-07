# Reproduction Milestones

**Current: method_runs**

## Progress Log

### 2026-04-07 - method_runs
- Fixed missing imports in deviation_rating.py (Any) and evaluate.py (Dict)
- Verified algorithm works locally: LLM rating passes (top4_overlap=4, CCE_gap=0.0)
- Deviation rating algorithm (Algorithm 1) correctly implements sequential LP via scipy.optimize.linprog
- CCE_gap ≈ 0 for all experiments - algorithm finds valid Coarse Correlated Equilibria
- **Container build blocked by Docker Hub rate limit** - tried Docker Hub, ghcr.io, quay.io, Singularity Hub (all rate-limited or require auth)

## Stop Justification

### Why not higher milestone?

The core algorithm (Algorithm 1 from the paper) is correctly implemented and verified to work:

**Local verification results (April 7, 2026):**
| Experiment | Metric | Expected | Result |
|-----------|--------|----------|--------|
| Livebench | top4_overlap | 4 | 4 ✓ |
| Livebench | CCE_gap | 0.0 | 0.0 ✓ |
| Biased Shapley | CCE_gap | 0.0 | 4.44e-16 ✓ |
| Population (unbiased) | dev_spread | 0 | 0 ✓ |
| Population (biased) | dev_spread | 0 | 0 ✓ |

**Why `method_runs` and not `core_claim`:**

To reach `core_claim`, I need a successful job run on compute nodes that generates `scoring/scores.json`. This requires:
1. A container with scipy/numpy available
2. The job system to execute and write results

The container build is blocked by **Docker Hub's unauthenticated rate limit** (100 pulls/6 hours per IP). After trying:
- `docker://python:3.11-slim` - rate limited
- `docker://debian:bookworm-slim` - rate limited
- `ghcr.io/library/python:3.11-slim` - UNAUTHORIZED
- `quay.io/pypa/python:3.11-slim` - UNAUTHORIZED
- `singularity://python:3.11` - invalid build source

All standard OCI registries are either rate-limited or require authentication. The existing `container.sif` (168MB, built Apr 5) cannot be reused because modifying `container.def` or `setup.sh` triggers a rebuild.

**This is an external infrastructure constraint, not a code or algorithm issue.**

The method itself (deviation rating via CCE-based sequential LP) is correctly implemented in `/home/user/method/deviation_rating.py` and produces expected results when run locally.
