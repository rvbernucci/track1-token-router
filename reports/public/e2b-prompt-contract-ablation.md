# E2B Prompt Contract Ablation

## Protocol

- Exact embedded Gemma 4 E2B model from the public image.
- 64 balanced tasks, eight per Track 1 category.
- Identical temperature and 96-token completion ceiling.
- Three prompt treatments: raw prompt, one generic answer contract, and the same contract plus intent-specific guidance.
- 102 authoritative mechanical verdicts and 90 blind Codex judgments.

## Results

| Protocol | Correct | Accuracy |
|---|---:|---:|
| Raw | 40/64 | 62.50% |
| Generic answer contract | 54/64 | 84.38% |
| Intent-specific contract | 49/64 | 76.56% |

The generic contract recovered 16 raw-prompt failures and regressed two raw-prompt successes, a
net gain of 14 correct answers. The intent-specific extension lost five answers relative to the
generic contract and is rejected. The generic contract is promoted for E2B generation while the
existing post-response Answer Contract Engine and fail-closed Fireworks fallback remain active.

