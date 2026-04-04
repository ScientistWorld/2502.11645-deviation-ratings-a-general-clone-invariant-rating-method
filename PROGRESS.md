# Progress

## What Works

- Deviation rating algorithm (Algorithm 1) implemented in method/deviation_rating.py using CVXPY with sequential LP solving
- Game data generators for all key experiments (biased Shapley, RPS, Livebench)
- Complete evaluation pipeline in eval/evaluate.py
- All three experiments ready: biased Shapley game, clone invariance, LLM rating
- Environment setup with CVXPY + ECOS/SCS solvers

## Results

- Not yet tested — submission pending

## Remaining

- Test the algorithm on compute node to verify it runs
- Verify deviation rating produces equal ratings on biased Shapley game
- Verify clone invariance property
- Verify LLM grouping on Livebench data
- Compare with paper's expected values

## Issues

- Bash tool is broken on the login node — cannot test locally before submission
- LP solver fallback chain (GLOP → ECOS → SCS) implemented for robustness
- Numerical stability managed through quantization (1e-10 precision)

## Deviations from Paper

- Livebench data is approximated from the paper's Figure 2c heatmap — exact numerical data not available
- The paper uses CVXPY + GLOP; we use CVXPY + ECOS/SCS as fallback
- Population study uses synthetic data rather than the paper's exact sampling
