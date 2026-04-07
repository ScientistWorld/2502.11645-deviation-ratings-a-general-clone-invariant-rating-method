# Scientist Constraints

This is a game-theoretic rating method, not a predictive model training task.

## Method

The scientist must implement a game-theoretic equilibrium-based rating algorithm.
This means:
- The method must compute ratings from equilibria (or equilibrium-derived quantities) in normal-form games.
- The core algorithm must use CCE-based deviation gains as the rating signal.
- Clone invariance must be preserved.

The scientist may NOT:
- Replace the equilibrium-based approach with a purely statistical method (e.g., simple Elo fitting, Bradley-Terry).
- Hardcode the paper's exact numbers.
- Use a different equilibrium concept that fundamentally changes the ratings.

## Data

The scientist must use the provided local games for evaluation.
No external datasets or additional game families may be introduced for the scored experiments.

## Evaluation Protocol

The scientist must evaluate on the same scored experiments:
- `biased_shapley_augmented`
- `clone_invariance`

## Compliance Checklist
- [ ] Method uses equilibrium-based rating (CCE deviation gains), not a purely statistical approach
- [ ] Clone invariance property is preserved
- [ ] Evaluation uses the provided local games
- [ ] Both scored experiments are evaluated
