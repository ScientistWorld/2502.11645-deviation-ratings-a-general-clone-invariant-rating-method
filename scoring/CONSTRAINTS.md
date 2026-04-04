# Scientist Constraints

This is a game-theoretic rating method — not a model to train. Scientists must work within the deviation rating framework.

## Method

The scientist must implement a game-theoretic equilibrium-based rating algorithm.
This means:
- The method must compute ratings from equilibria (or equilibrium-derived quantities) in normal-form games.
- The core algorithm must use CCE-based deviation gains as the rating signal.
- Clone invariance and offset invariance must be preserved — these are the paper's key contributions.

The scientist may NOT:
- Replace the equilibrium-based approach with a purely statistical method (e.g., simple Elo fitting, Bradley-Terry).
- Hardcode the paper's exact numbers.
- Use a different equilibrium concept that fundamentally changes the ratings.

## Data

The scientist must use the provided game data (Shapley game, Livebench model-task data) for evaluation.
No external datasets or additional game data may be introduced — the evaluation must be on the same games used in this reproduction.

## Evaluation Protocol

The scientist must evaluate on the same experiments:
- Biased Shapley game: deviation rating must give approximately equal ratings.
- Clone invariance: adding copies must not change existing ratings.
- Livebench: top 4 models should be grouped at the top.

## Compliance Checklist
- [ ] Method uses equilibrium-based rating (CCE deviation gains), not a purely statistical approach
- [ ] Clone invariance property is preserved
- [ ] Offset invariance property is preserved
- [ ] Evaluation uses the provided game datasets
- [ ] All three experiments (Shapley, clone invariance, Livebench) are evaluated
