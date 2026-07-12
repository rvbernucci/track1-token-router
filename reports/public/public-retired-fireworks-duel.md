# Public Retired Track 1 Fireworks Duel

## Decision

Retain Kimi as the default Fireworks model and use MiniMax for summarization. This policy produced valid answers on all 10 retired public tasks under a blind Codex 5.5 high-reasoning judgment.

## Protocol

- Dataset: 10 official retired Track 1 validation tasks.
- Models: `minimax-m3` and `kimi-k2p7-code`.
- Runtime parity: raw user prompt, no JSON envelope, temperature zero, `reasoning_effort=none`, and the production dynamic completion-token policy.
- Judge: Codex 5.5 with high reasoning, blinded candidate identities, independent validity decisions, and explicit contract checks.
- Objective answers were also recomputed mechanically by the judge.

## Results

| Model | Valid | Preferred wins | Total tokens | Completion tokens | Mean latency |
|---|---:|---:|---:|---:|---:|
| Kimi K2.7 Code | 10/10 | 3 | 1,730 | 1,117 | 1,694 ms |
| MiniMax M3 | 8/10 | 3 | 2,899 | 1,243 | 1,381 ms |

Four tasks were ties. MiniMax produced the preferred answer on both summarization tasks and one sentiment task. Kimi produced the preferred answer on two factual-comparison tasks and one RGB factual task. MiniMax's two invalid answers were truncated factual comparisons; Kimi had no invalid answer in this sample.

## Selected Policy

- `summarization`: MiniMax M3.
- All other observed categories: Kimi K2.7 Code.
- If a preferred model is absent from runtime `ALLOWED_MODELS`, fall through to an authorized available model.

The selected policy is 10/10 valid on this public sample. This is directional evidence, not a claim of 100% hidden-test accuracy.
