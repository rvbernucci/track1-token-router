# Raw Prompt And Answer Contract Ablation

Date: 2026-07-10

## Decision

Promote `raw-prompt-v1` for answer-model calls. Keep the Answer Contract Engine as the only task-specific formatting layer before official JSON serialization.

## Frozen Holdout

The comparison used the same 240 mechanically scored tasks: 60 each for factual Q&A, NER, sentiment and summarization. Both runs used `accounts/fireworks/models/kimi-k2p7-code`, temperature zero and the same dynamic completion-token policy.

| Metric | `m1-system-v1` | `raw-prompt-v1` | Delta |
|---|---:|---:|---:|
| raw correct | 180 / 240 | 180 / 240 | 0 |
| final correct after contract | 180 / 240 | 180 / 240 | 0 |
| accuracy | 75.0% | 75.0% | 0 pp |
| prompt tokens | 31,143 | 13,383 | -17,760 (-57.0%) |
| completion tokens | 3,053 | 3,053 | 0 |
| total Fireworks tokens | 34,196 | 16,436 | -17,760 (-51.9%) |
| answer differences | - | 0 / 240 | byte-identical |
| contract regressions | 0 | 0 | 0 |

The Answer Contract Engine normalized 60 outputs in each run, all canonical sentiment labels. This did not change the mechanical score because the evaluator already accepted those outputs after its own normalization.

## Singleton JSON Contract Recovery

Error decomposition showed that the entire 25-point deficit came from one NER schema mismatch, not entity extraction failure. Kimi returned correct entities as singleton arrays, such as `{"person":["Maya Chen"]}`, while the exact contract expected scalar strings, such as `{"person":"Maya Chen"}`.

The Answer Contract Engine now unwraps singleton JSON arrays only when all required keys are singular, every value contains exactly one primitive, and the prompt does not request arrays, lists or multiple values.

| Metric | Raw model output | After contract | Delta |
|---|---:|---:|---:|
| correct | 180 / 240 | 240 / 240 | +60 |
| accuracy | 75.0% | 100.0% | +25 pp |
| recovered answers | - | 60 | +60 |
| regressed answers | - | 0 | 0 |
| additional Fireworks tokens | - | 0 | 0 |

This result is limited to the four-category mechanical holdout. It demonstrates exact-contract recovery, not 100% expected accuracy on the hidden eight-category evaluation.

## Artifact Integrity

```text
m1-system-v1 candidates
0f361b0ba70d1bd0e03f7234c283fcba272d099bb746a3790a2e06e3e98a5413

raw-prompt-v1 candidates
35f470045b5058a55fc9bffb3a3467d8ae899da032da16c0f2cc397df58c89ee

raw-prompt-v1 contract report
23a226de35f528380e4fc910b094d3bdf1d79430d87b4323e266be7397b32b5c
```

The raw-prompt run cost `$0.02492585` in observed Fireworks billing.

## Scope

This promotes the clean prompt protocol for Kimi. It does not promote E2B: E2B must repeat the same fresh holdout on the AMD pod with `raw-prompt-v1`, the current Answer Contract Engine and the four-gigabyte runtime constraints.

## Concise System Prompt Rejection

We also tested this short system instruction:

```text
Follow the user's requested format exactly. Otherwise answer succinctly and precisely. Return only the answer.
```

| Metric | `raw-prompt-v1` | `concise-system-v1` | Delta |
|---|---:|---:|---:|
| accuracy | 75.0% | 75.0% | 0 pp |
| prompt tokens | 13,383 | 18,903 | +5,520 |
| completion tokens | 3,053 | 3,045 | -8 |
| total Fireworks tokens | 16,436 | 21,948 | +5,512 (+33.5%) |
| answer differences | - | 1 / 240 | 239 identical |

The only changed answer removed a Markdown fence around valid JSON. The Answer Contract Engine already performs that transformation locally at zero Fireworks tokens. `concise-system-v1` is therefore rejected.

```text
concise-system-v1 candidates
f8953fa605e0a9af3866240c16634beef72adcbd83589bf0c8c512fc04886401

concise-system-v1 contract report
ffc059b3b804959d37d007ff83edeb8b03557b26e090e2f373f6c8d08538a82a
```

## Compact Completion Caps

The `compact-contract-v2` policy reduced worst-case generation ceilings without changing any of the 240 answers:

| Family | Previous cap | Validated compact cap | Final runtime cap |
|---|---:|---:|---:|
| sentiment label | 48 | 8 | 8 |
| one-sentence summary | 48 | 48 | 48 |
| exact-key JSON NER | 104-106 | 96 | 96 |
| short access code | 256 | 64 | 24 |

All 60 access-code completions used exactly three tokens, so the final scalar ceiling was tightened from the validated 64 to 24 with substantial safety margin. Completion caps are risk bounds: they do not reduce scored tokens when the model already stops naturally.

```text
compact-cap candidates
896093591cee5c4f62901391af8d228738bde9cf9dd57a5a4998e485d3fddbc4

compact-cap contract report
8b74f4e84cbd786ee54ce2c78dee2b67183d2caed4370f1a4ba71b83a8871ec3
```
