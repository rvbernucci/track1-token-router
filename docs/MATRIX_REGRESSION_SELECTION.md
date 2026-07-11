# Matrix Regression Model Selection

> Historical note: this document describes the Fireworks matrix fallback developed before the final Sprint 63 intent policy. The final image gives enabled `fireworks-intent-policy-v2.json` precedence; the matrix remains a safe fallback when that preference is unavailable.

## Objective

Create an experimental layer to learn weights from real Fireworks microbenches.

The idea is not to replace Pareto/Nash immediately. The idea is to use matrix regression to calibrate the relationship between:

- task domain;
- model family;
- estimated capability;
- domain correlation;
- estimated tokens;
- estimated cost;
- estimated latency;
- reasoning mode;
- observed validity;
- real tokens/cost/latency.

## Formula

Cada candidato vira um vetor:

```text
x = [
  bias,
  tier flags,
  domain flags,
  capability,
  correlation,
  reliability,
  cost_utility,
  token_utility,
  latency_utility,
  nash_product,
  prisoner_payoff,
  family flags,
  family x domain interaction flags,
  reasoning flags
]
```

O alvo de treino combina validade e eficiencia observada:

```text
target =
  0.80 * valid
  + 0.18 * observed_token_utility
  + 0.02 * observed_latency_utility
```

Os coeficientes sao aprendidos por ridge regression:

```text
beta = inv(XT X + lambda I) XT y
```

No runtime experimental:

```text
regression_utility = clamp(beta dot x, 0, 1)
```

The `hybrid_score` changes by tier:

| Tier | Regression | Nash | Tokens | Cost USD |
| --- | ---: | ---: | ---: | ---: |
| `cheap` | 0.50 | 0.20 | 0.30 | 0.00 |
| `medium` | 0.65 | 0.15 | 0.20 | 0.00 |
| `strong` | 0.80 | 0.10 | 0.10 | 0.00 |

The competitive idea is simple: first pass the accuracy gate; then reduce tokens aggressively. When there are at least eight comparable observations, the model needs to reach `0.60` on the 95% Wilson lower bound. Price in dollars remains only as telemetry and a tiebreaker after accuracy and tokens, because it does not enter the official score.

`cost_utility` remains in the schema for compatibility with artifacts and historical traces, but its feature value is fixed at `0.0` in the fit and at runtime. Thus, a price list change cannot change the competitive route when accuracy, tokens, and latency remain the same.

## Artifacts

- Code: `router/orchestration/matrix_regression_selector.py`
- Offline fit: `scripts/fit_fireworks_matrix_regression.py`
- Track 1 weights used in Docker: `router/data/fireworks_track1_allowed_weights.json`
- Track 1 token-aligned report: `reports/generated/fireworks-track1-token-objective-regression.md`
- Real Fireworks results: `reports/generated/fireworks-track1-category-20260709-results.jsonl`, `reports/generated/fireworks-hidden-variant-results.jsonl`, `reports/generated/fireworks-championship-results.jsonl`, `reports/generated/fireworks-frontier-20260709-results.jsonl`, `reports/generated/fireworks-structure-heldout-20260709-results.jsonl`, `reports/generated/fireworks-escape-20260709-results.jsonl`

## Current Result

Track 1 training allowed with `183` useful rows, filtered from `567` raw rows:

- `minimax-m3`
- `kimi-k2p7-code`

The `ok=false` lines are excluded by default so as not to confuse access/transport errors with model quality. The weights also record `observed_models`; in the matrix runtime, allowed models with no completed calls during training are filtered out when there is an observed alternative. This avoids blindly choosing Gemma while serverless IDs continue to return `404` with the local key.

The weights now also record an empirical matrix `domain_model_stats` at two levels: `domain::structure` and `domain`. At runtime, each candidate receives adjustment by smoothed validity rate and confidence, first by specific structure, then by domain, and then by overall average. This prevents a cheap option with a poor history in that format from becoming the dominant strategy just due to cost/tokens.

The Docker weights were rebuilt on 2026-07-10 over the same `183` observations, replacing the old cost-oriented target with the official token-oriented target. Top coefficients learned in the current fit:

| Feature | Sign |
| --- | ---: |
| `bias` | positive |
| `capability` | negative |
| `shape_json_output` | positive |
| `shape_json_numeric` | negative |
| `shape_constrained_summary` | negative |
| `correlation` | positive |
| `interaction_kimi_code_generation` | negative |
| `domain_extraction` | negative |
| `interaction_minimax_code_generation` | positive |

Replay actual:

| Task | Selected Model |
| --- | --- |
| `factual_author` | `kimi-k2p7-code` |
| `summarization_tokens` | `kimi-k2p7-code` |
| `debug_first_even` | `minimax-m3` |
| `debug_is_adult` | `minimax-m3` |
| `code_gen_clamp` | `minimax-m3` |
| `math_discount_fee` | `minimax-m3` |
| `ner_money_date` | `minimax-m3` |
| `escape_code_last_digit` | `minimax-m3` |
| `escape_debug_average` | `minimax-m3` |
| `escape_factual_gold_symbol` | `kimi-k2p7-code` |
| `escape_summary_cache_latency` | `kimi-k2p7-code` |

## Competitive Analysis

The regression confirmed some strong signals:

- `kimi-k2p7-code` should win when the observed validity is comparable and the observed `usage.total` by domain/structure/model is smaller, especially in compact factual QA, summarization, logic, selected math, and formatting;
- `minimax-m3` gained weight as a robustness fallback, especially in code generation, code debug, structured extraction, mixed sentiment, and compound math when the calibrated score exceeds token savings;
- Gemma serverless remains unavailable with the local key, so the runner needs to try, cache the 404, and continue without locking up;
- family x domain interactions are necessary because a global average per model hides specializations.

## Current Limitation

The dataset is still small, but the regression is now active as a calibration layer of the main selector in Docker. It does not replace Nash: it combines it with the learned score.

The original `v1` discrete intent policy failed its historical gate and remains disabled. A separate final paired calibration produced `fireworks-intent-policy-v2.json`: Kimi by default and MiniMax for extraction. It matched MiniMax's 21/23 validity while reducing tokens from 3,869 to 1,967. The matrix remains the operational fallback when the preferred policy model is absent from runtime `ALLOWED_MODELS`.

Main gap:

- the runtime token estimation already mixes the theoretical profile with the observed `avg_total_tokens` by domain/structure/model, weighted by sample confidence;
- the frontier and structure-heldout microbenches showed that verbosity and validity vary by family and prompt format;
- the next step is to separate `prompt_tokens` and `completion_tokens` when the provider returns these fields stably, to better calibrate long responses.

## Next Step

Implement a second regression when there is sufficient sample size:

```text
predicted_completion_tokens = f(model_family, domain, tier, reasoning_mode)
```

With this, Pareto stops using only the observed `avg_total_tokens` and starts estimating expected tokens per component:

```text
expected_scored_tokens =
  prompt_tokens
  + predicted_completion_tokens
```

Price per token remains recorded for development credit monitoring, but does not enter this score function.
