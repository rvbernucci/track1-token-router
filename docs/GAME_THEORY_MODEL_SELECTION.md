# Game Theory Model Selection

## Objective

This layer transforms model selection into a competitive game between quality and cost.

Track 1 penalizes two symmetrical errors:

- calling a model that is too strong for a simple task;
- calling a model that is too cheap and losing accuracy.

The selector now treats these errors as a prisoner's dilemma: each decision can cooperate with the global goal or defect to a locally attractive strategy.

## Players

The game has three interests:

- `accuracy_player`: maximize response adherence to the task domain.
- `token_budget_player`: minimize Fireworks input/output cost.
- `latency_tiebreaker`: break ties in favor of lower latency without dominating cost/quality.

The chosen equilibrium is the pure strategy with the highest Nash product within the eligible frontier.

## Correlation Matrix

Each task is mapped to a domain:

- `classification`
- `formatting`
- `summarization`
- `extraction`
- `logic`
- `math_reasoning`
- `code_debug`
- `code_generation`
- `current_factual`
- `general`

Each model has strengths:

- `general`
- `classification`
- `formatting`
- `summarization`
- `logic`
- `math_reasoning`
- `code_generation`
- `code_debug`
- `reasoning`
- `agentic`
- `embedding`
- `reranker`

The `DOMAIN_CORRELATION_MATRIX` calculates the fit between task domain and model strengths. Examples:

| Task Domain | Model Strength | Correlation |
| --- | --- | --- |
| `code_generation` | `code_generation` | `1.00` |
| `code_generation` | `code_debug` | `0.85` |
| `code_generation` | `agentic` | `0.75` |
| `logic` | `math_reasoning` | `0.85` |
| `summarization` | `extraction` | `0.70` |
| `classification` | `general` | `0.55` |
| any chat | `embedding`/`reranker` | `0.00` for final response |

This matrix prevents a common error: comparing models solely by price when they are not equally correlated with the task.

## Utilities

Each candidate receives three normalized utilities:

```text
cost_utility = inverse_range(estimated_cost_usd)
latency_utility = inverse_range(latency_ms)
quality_utility =
  0.50 * capability_ratio
  + 0.30 * domain_correlation
  + 0.20 * reliability
```

`capability_ratio` is truncated at `1.0`. Once the model passes the minimum floor, the game does not infinitely reward larger models. This avoids over-escalation.

## Weights By Tier

| Tier | Cost | Quality | Latency |
| --- | ---: | ---: | ---: |
| `cheap` | `0.65` | `0.25` | `0.10` |
| `medium` | `0.50` | `0.35` | `0.15` |
| `strong` | `0.40` | `0.50` | `0.10` |

Interpretation:

- in `cheap`, cost dominates because the task should be almost mechanical;
- in `medium`, quality gains weight, but cost still leads;
- in `strong`, quality leads, but cost still decides between sufficiently good models.

## Nash Product

The main score is:

```text
nash_product =
  cost_utility ^ cost_weight
  * quality_utility ^ quality_weight
  * latency_utility ^ latency_weight
```

The chosen model is:

```text
max(nash_product, prisoner_payoff, -estimated_cost_usd, -latency_ms)
```

Only chat-capable and eligible candidates compete in the final decision.

## Prisoner's Dilemma

Each candidate receives a strategic label:

| Label | Meaning |
| --- | --- |
| `cooperate_token_efficient` | model passes the quality floor and is close to the lowest eligible cost |
| `cooperate_quality_safe` | model passes the quality floor but is not the lowest cost |
| `defect_unsafe_underqualified` | model is too cheap for the domain |
| `defect_expensive_overescalation` | strong model, but too expensive for marginal quality gain |
| `dominated_strategy` | another model exists that is better or equal in cost/latency/capability/reliability |
| `non_chat_auxiliary_strategy` | embedding/reranker; can help RAG, but does not produce the final response |

## Practical Example

Input:

```text
Write a function that parses nested JSON and handles edge cases.
```

Domain:

```text
code_generation
```

In the current full catalog:

- `minimax-m3`: correlation `1.0`, passes strong floor, low cost, becomes `cooperate_token_efficient`.
- `kimi-k2p7-code`: correlation `1.0`, high quality, but much higher cost, becomes `defect_expensive_overescalation`.
- `gpt-oss-20b`: very low cost, but insufficient capability, becomes `defect_unsafe_underqualified`.
- `qwen3-embedding-8b`: not chat-capable, becomes `non_chat_auxiliary_strategy`.

Equilibrium:

```text
accounts/fireworks/models/minimax-m3
```

This does not mean that M3 is "better" than Kimi in an absolute sense. It means that, in this specific game, it is the best strategic response given the token/accuracy scoring.

## Where This Lives In The Code

File:

```text
router/orchestration/fireworks_model_router.py
```

Fields included in each candidate:

- `correlation`
- `quality_utility`
- `cost_utility`
- `latency_utility`
- `nash_product`
- `prisoner_payoff`
- `game_label`

Selection summary:

- `game_theory.selection_rule`
- `game_theory.equilibrium_model`
- `game_theory.equilibrium_type`
- `game_theory.tier_weights`
- `game_theory.selected_nash_product`
- `game_theory.selected_prisoner_payoff`
- `game_theory.selected_correlation`

## Competitive Rule

If two models are sufficiently good, the one that cooperates best with the global objective wins: accuracy above the floor with the lowest token cost.

If a cheap model does not pass the floor, it is not a saving; it is a risk.

If an expensive model does not materially improve quality, it is not safety; it is over-escalation.
