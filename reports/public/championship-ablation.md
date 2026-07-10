# Championship Ablation

Routes, features, coefficients and prompts were selected on validation only. The locked test was disclosed once and used only as a predeclared pass/fail promotion gate.

Validation-selected champion: `deterministic_then_kimi`

| Variant | Split | Accuracy | Binary accuracy | Fireworks tokens | Avg tokens | Local answers |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `deterministic_then_kimi` | test | 0.596 | 0.750 | 73870 | 257.4 | 0 |
| `deterministic_then_kimi` | validation | 0.585 | 0.703 | 73825 | 259.9 | 0 |
| `fireworks_kimi` | test | 0.596 | 0.750 | 73870 | 257.4 | 0 |
| `fireworks_kimi` | validation | 0.585 | 0.703 | 73825 | 259.9 | 0 |
| `fireworks_minimax` | test | 0.505 | 0.707 | 101447 | 353.5 | 0 |
| `fireworks_minimax` | validation | 0.567 | 0.700 | 101466 | 357.3 | 0 |
| `matrix_pareto_nash` | test | 0.578 | 0.751 | 78853 | 274.7 | 0 |
| `matrix_pareto_nash` | validation | 0.574 | 0.688 | 80988 | 285.2 | 0 |
| `rejected_e2b_challenger` | test | 0.547 | 0.744 | 57103 | 199.0 | 88 |
| `rejected_e2b_challenger` | validation | 0.585 | 0.703 | 73825 | 259.9 | 0 |
| `validation_intent_candidate` | test | 0.561 | 0.732 | 81474 | 283.9 | 0 |
| `validation_intent_candidate` | validation | 0.592 | 0.709 | 79717 | 280.7 | 0 |

## Decision

Final runtime: `deterministic_then_kimi`
Preferred allowed model: `accounts/fireworks/models/kimi-k2p7-code`
FunctionGemma bundled: `False`
E2B bundled: `False`

The deterministic layer is fail-closed and preserves the validation-selected Kimi baseline; local E2B, per-intent routing and matrix routing failed their frozen promotion comparisons.

The local models remain reproducible research artifacts, but bundling a rejected route would increase image size, startup time and failure surface without measured token savings.
