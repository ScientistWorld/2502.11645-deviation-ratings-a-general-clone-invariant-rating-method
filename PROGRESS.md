# Progress

## What Works
- Deviation rating algorithm using scipy.optimize.linprog (HiGHS method)
- Game data generators: biased Shapley, RPS, Livebench, population study
- Complete evaluation pipeline
- Livebench top4_overlap=4/4 (correct!)
- Population study: dev spread=0 (correct!)

## Results (from last test)
| Experiment | Metric | Expected | Got |
|---|---|---|---|
| Biased Shapley | CCE_gap | 0.0 | -0.63 (ECOS failed) |
| Clone Invariance | max_diff | 0.0 | 1.64 (ECOS failed) |
| Livebench | top4_overlap | 4 | 4 ✓ |
| Livebench | CCE_gap | ~0 | -0.0004 |
| Population | dev_spread | 0 | 0 ✓ |

## Issues
- ECOS/CVXPY numerical instability on small games (3x3 Shapley)
- Fix: scipy.optimize.linprog with HiGHS — more reliable for small LPs

## Remaining
- Verify scipy-based implementation gives CCE_gap=0 on Shapley
- Verify clone invariance with scipy
- Verify Livebench still works
- Update reference.json targets with correct expected values
