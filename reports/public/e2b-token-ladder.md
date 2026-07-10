# Gemma E2B Token-Ladder Evidence

Updated: 2026-07-10

## Result

The official mixed 2/4/8-bit Gemma 4 E2B LiteRT-LM artifact was evaluated with staged local output ceilings. Only tasks not unanimously approved by independent Minimax M3 and Kimi K2.7 Code judges advanced to the next ceiling.

| First approved ceiling | Newly approved | Cumulative | Deterministic fit | Format complexity | Generation demand | Knowledge uncertainty | Reasoning demand |
|---|---:|---:|---:|---:|---:|---:|---:|
| 96 | 15 | 15 | 2.67 | 3.67 | 3.47 | 0.53 | 3.80 |
| 192 | 10 | 25 | 3.10 | 5.00 | 3.50 | 0.70 | 4.60 |
| 384 | 8 | 33 | 3.25 | 4.00 | 3.12 | 0.50 | 4.38 |
| not approved by 384 | 60 | 33 | 2.72 | 5.93 | 5.20 | 0.65 | 5.07 |

The raw 192-token approvals include three cases whose answers were byte-for-byte identical to their 96-token answers. These are judge variance, not token-budget recovery. The stricter marginal frontier therefore contains seven genuine 96 -> 192 recoveries and eight genuine 192 -> 384 recoveries. The 384-token recoveries were limited to three NER, two debugging and three math tasks. Code generation remained the largest failed family with 15 cases.

| Transition | Retried | Genuine recovery | Judge-only flip | Genuine recovery rate |
|---|---:|---:|---:|---:|
| 96 -> 192 | 78 | 7 | 3 | 8.97% |
| 192 -> 384 | 68 | 8 | 0 | 11.76% |

| Intent | At 96: correct / tested | At 192: recovered / retried | At 384: recovered / retried |
|---|---:|---:|---:|
| Code debugging | 1 / 9 | 1 / 8 | 2 / 7 |
| Code generation | 1 / 17 | 1 / 16 | 0 / 15 |
| Factual Q&A | 2 / 7 | 0 / 5 | 0 / 5 |
| Logic puzzle | 3 / 15 | 2 / 12 | 0 / 10 |
| Math reasoning | 1 / 14 | 1 / 13 | 3 / 12 |
| NER | 2 / 14 | 1 / 12 | 3 / 11 |
| Sentiment | 4 / 7 | 1 / 3 | 0 / 2 |
| Summarization | 1 / 10 | 3 / 9 | 0 / 6 |

These are conditional recovery counts, not standalone category accuracy. The retry population becomes progressively harder at each stage.

## Interpretation

- Higher token ceilings recover some tasks, but do not make E2B a general solver: 60 of 93 tasks remained unapproved.
- Failure is associated more strongly with combined format, generation and reasoning demand than with intent alone.
- Knowledge uncertainty was low in every group, so this calibration set cannot support a strong claim about current or open-domain facts.
- A 384-token route should be exceptional and family-conditioned, not a default continuation after 192.
- The 192-token route is most promising for constrained summarization and short logic tasks; the 384-token route has evidence only for NER, debugging and math.
- The router should learn `P(correct | intent, five scores, token ceiling)` from held-out outcomes rather than use a single hand-written threshold.

## Runtime Audit

The stock LiteRT server selected GPU by default, so the initial ladder latencies were quarantined. A project-owned server then forced CPU, two threads and context 2048. The standard artifact completed 93/93 at 96 tokens with p50 `4.22 s` and p95 `7.09 s`; its CPU outputs were identical to the initial standard-artifact outputs.

The 96-token CPU pass consumed `393.22 s` in aggregate. Under the ten-minute global deadline, larger ceilings must therefore be assigned selectively rather than applied to every task.

The smaller 2.0 GB Web artifact was rejected after 93/93 forced-CPU engine failures. Speculative decoding improved mean latency by `1.17x` on 12 long-output tasks, but remains experimental pending positive-case and 4 GB memory validation.

Detailed task-level profiles remain internal under `reports/generated/amd-pod-scale789/token-ladder/`.
