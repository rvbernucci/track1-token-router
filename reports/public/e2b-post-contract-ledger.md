# E2B Post-Contract Ledger

All 1,991 E2B answers were passed through Answer Contract Engine v2 and assigned a conservative final verdict.

## Totals

| Verdict | Rows | Rate |
|---|---:|---:|
| correct | 728 | 36.6% |
| incorrect | 659 | 33.1% |
| uncertain | 604 | 30.3% |

Format valid: 913/1991 (45.9%).

## By Category

| Category | Correct | Incorrect | Uncertain | Total |
|---|---:|---:|---:|---:|
| code_debugging | 52 | 92 | 95 | 239 |
| code_generation | 55 | 135 | 81 | 271 |
| factual_qa | 110 | 47 | 46 | 203 |
| logic_puzzle | 78 | 82 | 96 | 256 |
| math_reasoning | 43 | 112 | 105 | 260 |
| ner | 151 | 93 | 53 | 297 |
| sentiment | 156 | 43 | 49 | 248 |
| summarization | 83 | 55 | 79 | 217 |

## Interpretation

Unchanged answers inherit their original Gemini+Kimi judgment because their bytes did not change. Changed answers use a fresh majority of Codex, Gemini and Kimi. `uncertain` is not counted as correct. This ledger measures the current frozen E2B candidate set; it is not a hidden-hackathon accuracy estimate.
