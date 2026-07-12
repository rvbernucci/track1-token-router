# Fireworks Champion v3

## Decision

**Retain the existing runtime policy. Do not promote a Sprint 76 policy v3.**

The arena completed all 1,600 paired calls over 800 prompts and all 334 semantic judge rows. However, it did not satisfy the promotion gates and its original selection protocol included 170 final-holdout prompts before a policy was frozen. The results remain useful comparative evidence, but they are not a leakage-safe promotion basis.

## Frozen Arena

- 800 unique tasks and lineages, with 100 tasks in each official category.
- 400 tasks from E2B expansion v1 and 400 from regression v2.
- 1,600 responses: Kimi K2.7 Code and MiniMax M3 on every task.
- Zero provider failures; recorded Fireworks spend was approximately $0.51.
- Mechanical-first adjudication followed by 334 blinded Codex 5.5 decisions.

## Results

| Policy | Correct | Accuracy | Tokens |
|---|---:|---:|---:|
| Always Kimi | 378/800 | 47.25% | 188,077 |
| Always MiniMax | 408/800 | 51.00% | 261,613 |
| Evidence-supported category policy | 400/800 | 50.00% | 202,329 |

The paired comparison supports MiniMax over Kimi for logic puzzles (`p=0.00813`) and sentiment (`p=0.01562`). No other category difference reached `p<0.05`. These findings informed later targeted experiments, but the Sprint 76 arena itself failed the required 95% global accuracy and 90% per-category floors.

## Protocol Limitations

- The arena retained split labels but aggregated development and 170 final-holdout rows during policy estimation. The holdout therefore cannot serve as a sealed promotion audit.
- Only exact references, JSON parsing and truncation received hard mechanical verdicts; the planned executable-code, general-logic and complete NER validators were not all present.
- No second independent semantic-judge pass or lineage-grouped bootstrap confidence interval was completed.
- Difficulty reporting is incomplete for regression-v2 rows because their source metadata does not provide a difficulty label.

## Reproducibility

- Dataset manifest: `evals/fireworks-champion-v3/manifest.json`
- Frozen tasks: `evals/fireworks-champion-v3/tasks.jsonl`
- Responses: `reports/generated/fireworks-champion-v3/responses.jsonl`
- Final verdicts: `reports/generated/fireworks-champion-v3/final-verdicts.jsonl`
- Machine-readable summary: `reports/generated/fireworks-champion-v3/summary.json`

No `configs/fireworks-intent-policy-v3.json` is produced. This is intentional: the promotion gates failed.
