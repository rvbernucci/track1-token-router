# Fireworks Accuracy-First Completion-Cap Ablation

## Question

Can ProofRoute recover correct answers by increasing completion headroom without changing the
model, temperature, raw user prompt, routing policy, or Answer Contract Engine?

## Protocol

- Cohort: 159 unique frozen arena tasks, approximately 20 per Track 1 category.
- Composition: 80 frozen failures and 79 frozen successes.
- Models: the same category-selected Kimi or MiniMax model used by the frozen baseline.
- Prompt: byte-identical raw user prompt with no new system message.
- Change under test: completion cap only.
- Adjudication: deterministic hard verdicts first, followed by 72 randomized blind comparisons
  judged by Codex `gpt-5.5` with high reasoning.

## Results

| Category | Frozen correct | Cap-only correct | Rescues | Regressions |
|---|---:|---:|---:|---:|
| Code debugging | 10/20 | 14/20 | 5 | 1 |
| Code generation | 10/20 | 10/20 | 1 | 1 |
| Factual Q&A | 10/20 | 11/20 | 1 | 0 |
| Logic puzzles | 10/20 | 10/20 | 0 | 0 |
| Math reasoning | 10/20 | 10/20 | 0 | 0 |
| NER | 10/20 | 10/20 | 1 | 1 |
| Sentiment | 10/19 | 11/19 | 1 | 0 |
| Summarization | 10/20 | 14/20 | 4 | 0 |
| **Total** | **80/159** | **90/159** | **13** | **3** |

The cap-only policy produced a net gain of ten correct answers, or 6.29 percentage points on
this paired cohort. Because the prompt and model were unchanged, this isolates completion
headroom as the causal treatment. The run used 48,098 total Fireworks tokens: 31,233 prompt and
16,865 completion tokens. Eighteen responses still ended at the tested cap.

## Promotion

The runtime completion policy is promoted from `compact-contract-v3` to
`accuracy-first-contract-v4`:

- code: up to 512 tokens;
- logic and extraction: up to 384 tokens;
- math: 128-192 tokens for number contracts and up to 192 otherwise;
- factual and summarization: up to 256 tokens;
- classification and short strict contracts retain bounded caps but receive enough headroom for
  model-internal generation before the Answer Contract Engine produces the final form.

Accuracy remains the first gate. The configured ceiling does not itself spend tokens; Fireworks
scores actual generated tokens, and the Answer Contract Engine still returns the shortest valid
final answer.
