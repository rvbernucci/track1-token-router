# Sprint 80 Fireworks Prompt and Cap Ablation

## Decision

Promote a domain-aware prompt policy, not a global prefix and not an uncapped completion policy.

- `formatting` and `extraction`: prepend `Answer succinctly and follow the requested format exactly:\n`.
- `current_factual` and `math_reasoning`: prepend `Answer succinctly:\n`.
- All other domains: preserve the raw prompt.
- Keep the existing contract-aware completion caps. Do not globally raise them to 1,024.
- Prefer Kimi as the primary Fireworks model and retain MiniMax as an authorized fallback.

## Evidence

The first paired experiment covered 10 retired public tasks and 6 objective tasks across Kimi and MiniMax (96 calls).

| Model / policy | Objective | Total tokens | Truncations |
|---|---:|---:|---:|
| Kimi raw policy | 5/6 | 2,086 | 0 |
| Kimi succinct policy | 5/6 | 1,396 | 0 |
| Kimi succinct + 1,024 | 5/6 | 1,415 | 0 |
| MiniMax raw policy | 5/6 | 4,210 | 2 |
| MiniMax succinct policy | 5/6 | 3,385 | 0 |
| MiniMax succinct + 1,024 | 5/6 | 3,406 | 0 |

On the 10 public tasks alone, Kimi's succinct prefix reduced total tokens from 1,827 to 1,114 (39.0%) and kept every response complete. Raising the cap to 1,024 increased usage to 1,133 without a quality or truncation benefit.

The second experiment covered 130 unique objective tasks from all eight local Fireworks microbench suites (780 calls).

| Model / prompt | Correct | Accuracy | Total tokens |
|---|---:|---:|---:|
| Kimi raw | 121/130 | 93.08% | 5,964 |
| Kimi global succinct | 119/130 | 91.54% | 6,431 |
| Kimi global format-safe | 124/130 | 95.38% | 7,210 |
| Kimi domain-aware hybrid | 127/130 | 97.69% | 6,228 |
| MiniMax raw | 115/130 | 88.46% | 19,588 |
| MiniMax global succinct | 117/130 | 90.00% | 19,917 |
| MiniMax global format-safe | 117/130 | 90.00% | 20,692 |

The Kimi hybrid gains six correct answers over raw for 264 additional tokens (4.4%). Its three remaining failures are one NER decimal-format case, one code-generation case blocked by the validator's import policy, and one exact-term summarization case.

## Exact recommended production patch

1. Add a Fireworks message builder that receives the original `TaskEnvelope` and the selected domain.
2. For `formatting` or `extraction`, return one user message containing `Answer succinctly and follow the requested format exactly:\n{raw_prompt}`.
3. For `current_factual` or `math_reasoning`, return one user message containing `Answer succinctly:\n{raw_prompt}`.
4. Otherwise return the existing raw user message unchanged.
5. Replace only `build_m1_messages(task)` in `FireworksDirectRunner` with this domain-aware builder.
6. Preserve `_completion_token_policy`; do not set a global 1,024-token ceiling.
7. Make Kimi the first candidate when it is present in `ALLOWED_MODELS`; keep MiniMax as fallback.

Raw evidence is stored in `results.json` here and in `../s80-fireworks-objective-ablation/results.json`.
