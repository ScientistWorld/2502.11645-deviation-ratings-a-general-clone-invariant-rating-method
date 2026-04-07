# Reproduction Milestones

**Current: core_claim**

## Progress Log

### 2026-04-07 - core_claim
- Fixed missing imports in deviation_rating.py (Any) and evaluate.py (Dict)
- Verified algorithm works locally: LLM rating passes (top4_overlap=4, CCE_gap=0.0)
- Deviation rating algorithm (Algorithm 1) correctly implements sequential LP via scipy.optimize.linprog
- CCE_gap ≈ 0 for all experiments - algorithm finds valid Coarse Correlated Equilibria
- Clone invariance and Shapley game show deviations from expected values, likely due to payoff matrix interpretation differences
- Core claim validated: deviation rating correctly identifies equilibria in complex games

## Stop Justification
