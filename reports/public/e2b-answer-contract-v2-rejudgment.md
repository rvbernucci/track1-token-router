# E2B Answer Contract v2 Rejudgment

Date: 2026-07-10

## Scope

The frozen AMD-pod artifact contains 1,991 E2B candidates generated with a 96-token ceiling. Answer Contract Engine v2 changed 261 candidates and left 1,730 byte-identical. Only the changed delta was re-judged.

Post-contract judge coverage is complete:

| Judge | Rows | Billing |
|---|---:|---:|
| Codex subscription default | 261 | $0 API |
| Gemini 3.5 Flash Medium via Antigravity | 261 | $0 API |
| Kimi K2.7 Code via Fireworks | 261 | $0.117886 |
| Total judgments | 783 | $0.117886 |

Claude Code was not used.

## Three-Judge Result

| Consensus | Rows |
|---|---:|
| unanimous correct | 117 |
| majority correct | 24 |
| unanimous incorrect | 86 |
| majority incorrect | 29 |
| unanimous/majority uncertain | 3 |
| no majority | 2 |

The majority estimate is therefore 141 correct, 115 incorrect and 5 unresolved among the 261 transformed candidates. This is a post-treatment quality estimate, not a causal recovery count.

## Comparable Before/After Policy

The original matrix used Gemini plus Kimi. Reapplying that same two-judge unanimous policy gives the fairest available comparison:

| Metric | Before contract | After contract | Delta |
|---|---:|---:|---:|
| unanimous correct | 132 | 131 | -1 |
| unanimous incorrect | 60 | 86 | +26 |
| judge disagreement/uncertain | 69 | 44 | -25 |
| format valid according to both judges | 143 | 193 | +50 |
| format invalid according to both judges | 45 | 50 | +5 |
| format disagreement | 73 | 18 | -55 |

The one-row correctness delta is within observed LLM-judge variance. Paired verdicts oscillated even for transformations that only removed a Markdown fence. The robust conclusion is that v2 substantially increases format agreement while semantic accuracy remains effectively flat.

## Majority Correct By Category

| Category | Correct | Incorrect | Unresolved | Changed rows |
|---|---:|---:|---:|---:|
| factual Q&A | 10 | 9 | 1 | 20 |
| math reasoning | 12 | 20 | 1 | 33 |
| sentiment | 27 | 10 | 2 | 39 |
| summarization | 12 | 8 | 0 | 20 |
| NER | 51 | 16 | 1 | 68 |
| code debugging | 10 | 10 | 0 | 20 |
| logic puzzles | 11 | 5 | 0 | 16 |
| code generation | 8 | 37 | 0 | 45 |

## Decision

Keep Answer Contract Engine v2 promoted. It improves contract adherence without a measurable semantic gain or loss. Do not use contract validity as proof that an E2B answer is correct. The router should be most conservative for code generation and math, and can be more permissive for NER, sentiment and logic when the local confidence model agrees.

Artifacts:

- `e2b-candidates-96-contract-v2.jsonl`: all 1,991 post-contract candidates;
- `e2b-candidates-96-contract-v2-changed.jsonl`: the 261-row delta;
- `judgments-contract-v2-fireworks-kimi.jsonl`: complete Kimi judgments;
- `judgments-contract-v2-agy.jsonl`: complete Gemini judgments;
- `judgments-contract-v2-codex-smoke.jsonl`: complete Codex judgments (the historical filename retains `smoke`).
