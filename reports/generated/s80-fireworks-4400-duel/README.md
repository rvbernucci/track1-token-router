# Sprint 80 Fireworks Kimi vs MiniMax Paired Duel

## Decision

- Default: `Kimi K2.7 Code`.
- Statistically supported override: `MiniMax M3` for `logic_puzzle`.
- Do not route by answer length alone: long-form accuracy was nearly tied.
- MiniMax for sentiment, math and NER remains candidate-only because paired evidence did not clear `p < 0.05`.
- Keep the domain-aware succinct prompt policy; do not use a global prefix or remove completion caps.

## Experiment

- 800 prompts from the 4,400-task corpora, 100 per Track 1 category, with 400 newly stratified prompts plus 400 legacy prompts whose difficulty is unspecified.
- 1,600 successful Fireworks calls, no failures.
- Mechanical-first validation plus blind Codex 5.5 high-reasoning adjudication for 381 semantic cases.
- Fireworks spend: `$0.595697`.

## Overall

| Model | Correct | Accuracy | Tokens | Truncations | Median latency |
|---|---:|---:|---:|---:|---:|
| kimi-k2p7-code | 412/800 | 51.50% | 204,202 | 112 | 1919 ms |
| minimax-m3 | 426/800 | 53.25% | 275,916 | 108 | 2122 ms |

Overall paired discordance: Kimi-only `44`, MiniMax-only `58`, McNemar `p=0.19779`.

## By category

| Category | Kimi | MiniMax | Kimi-only | MiniMax-only | p | Recommended |
|---|---:|---:|---:|---:|---:|---|
| code_debugging | 67/100 | 65/100 | 7 | 5 | 0.77441 | Kimi |
| code_generation | 41/100 | 35/100 | 13 | 7 | 0.26318 | Kimi |
| factual_qa | 78/100 | 77/100 | 2 | 1 | 1.00000 | Kimi |
| logic_puzzle | 16/100 | 30/100 | 7 | 21 | 0.01254 | MiniMax |
| math_reasoning | 18/100 | 22/100 | 0 | 4 | 0.12500 | Kimi |
| ner | 26/100 | 27/100 | 6 | 7 | 1.00000 | Kimi |
| sentiment | 87/100 | 93/100 | 1 | 7 | 0.07031 | Kimi |
| summarization | 79/100 | 77/100 | 8 | 6 | 0.79053 | Kimi |

## By expected reference length

| Length | N | Kimi | MiniMax | p |
|---|---:|---:|---:|---:|
| short_0_5 | 400 | 199/400 (49.75%) | 223/400 (55.75%) | 0.00072 |
| medium_6_30 | 215 | 125/215 (58.14%) | 118/215 (54.88%) | 0.18925 |
| long_31_plus | 185 | 88/185 (47.57%) | 85/185 (45.95%) | 0.72833 |

The apparent MiniMax advantage on short answers is confounded by logic and sentiment. Excluding those categories leaves Kimi at `96/216` and MiniMax at `101/216` (`p=0.26685`), so length alone is not a supported routing feature.

## By difficulty

| Difficulty | N | Kimi | MiniMax | p |
|---|---:|---:|---:|---:|
| easy | 136 | 91/136 (66.91%) | 86/136 (63.24%) | 0.26685 |
| moderate | 136 | 65/136 (47.79%) | 65/136 (47.79%) | 1.00000 |
| hard | 128 | 55/128 (42.97%) | 59/128 (46.09%) | 0.38770 |
| unspecified | 400 | 201/400 (50.25%) | 216/400 (54.00%) | 0.08168 |

## Reconciliation

The earlier MiniMax aggregate win was real but was concentrated in logic and sentiment. The recent objective sample favored Kimi because it over-represented short contract-sensitive tasks and used a domain-aware prompt policy. This larger paired run shows that output length is not a stable routing feature by itself; category and answer contract are more informative.
