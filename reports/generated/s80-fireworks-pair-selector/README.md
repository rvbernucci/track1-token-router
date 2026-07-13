# Sprint 80 Fireworks Pair Selector

## Decision

**Do Not Promote.** The challenger does not dominate `intent-policy-v2` on the protected holdout.

| Policy | Correct | Accuracy | Tokens |
|---|---:|---:|---:|
| intent-policy-v2 | 76/170 | 44.71% | 46,327 |
| learned challenger | 76/170 | 44.71% | 46,327 |

Holdout delta: **+0.00% accuracy**, **+0 tokens**.

## Protocol

- Inputs: raw FunctionGemma intent and five scores, prompt/mechanical features, expected contract, and expected response-length class.
- Fit boundary: only `fit` and `calibration`; `protected_holdout` is used once for the final report.
- Labels explicitly preserve `both_correct`, `both_incorrect`, `kimi_only`, and `minimax_only`; either model wins an accuracy tie.
- Overrides require an exact paired McNemar advantage after Holm family-wise correction.
- Objective is lexicographic: accuracy first, tokens second.

## Supported Rules

- No override survived the leakage-safe statistical gates.

## Data Sources

- `reports/generated/fireworks-champion-v3`: usable (1600 responses, 1600 verdicts)
- `reports/generated/s80-fireworks-4400-duel`: pending_labels (1512 responses, 0 verdicts)

The S80 4,400 duel is automatically ingested once a sibling `final-verdicts.jsonl` exists. Responses without verdicts are reported as pending and never treated as labels.

## Minimal Runtime Evaluator

The candidate artifact is `candidate-artifact.json` (SHA-256 `e8ce9660b6244413eb058ed258cda9065c544f2a0378778cca6548fc36850d58`). A production evaluator would deserialize it once, reuse already-computed FunctionGemma/mechanical features, apply the ordered predicates, and intersect the selected model with `ALLOWED_MODELS`. It needs no ML framework and no additional model inference.
