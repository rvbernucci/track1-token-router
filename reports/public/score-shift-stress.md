# FunctionGemma Score-Shift Stress

Every one of the five assessment scores was independently replaced with 0, 2, 4, 6, 8 and 10 for each valid frozen validation/test task.

- tasks: `569`
- perturbed decisions: `17070`
- route changes: `0`
- unsafe local selections: `0`
- route counts: `{"fireworks": 17070}`
- maximum Fireworks probability shift: `0.527808`

Score perturbations cannot reactivate E2B. The rejected research selector remains Fireworks-safe, and the promoted runtime removes FunctionGemma scores from its decision surface entirely.
