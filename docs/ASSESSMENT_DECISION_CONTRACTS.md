# Assessment And Decision Contracts

Updated: 2026-07-09

## Scope

Sprint 45 separates model perception from mathematical execution choice:

```text
untrusted task
-> TaskAssessment v1
-> code-computed structural features
-> canonical FeatureVector v1
-> outcome predictions
-> EngineDecision
```

FunctionGemma can emit only `intent` and the five scores. `sub_intent` remains labeling metadata and is not a runtime target. `engine`, `route`, `model`, `confidence` and `answer` are forbidden additional fields. Any malformed or out-of-taxonomy assessment produces an explicit Fireworks-safe decision.

Authoritative artifacts:

- `schemas/task-assessment-v1.schema.json`;
- `schemas/feature-vector-v1.schema.json`;
- `schemas/engine-outcome-v1.schema.json`;
- `schemas/routing-trace-v1.schema.json`;
- `router/core/contracts.py`;
- `router/orchestration/assessment.py`.

## Versioned Taxonomy

Assessment schema: `task-assessment-v1`
Sub-intent taxonomy: `track1-sub-intents-v1`

| Intent | Sub-intents |
|---|---|
| `factual_qa` | `stable_fact`, `current_fact`, `context_qa`, `open_domain_fact` |
| `math_reasoning` | `arithmetic`, `percent_fee_math`, `proportional_rate`, `numeric_compare`, `algebra`, `geometry`, `probability`, `statistics`, `other_math` |
| `sentiment` | `polarity`, `aspect_sentiment` |
| `summarization` | `constrained_summary`, `extractive_summary`, `abstractive_summary` |
| `ner` | `entity_extract`, `typed_entity_extract` |
| `code_debugging` | `python_debug`, `javascript_debug`, `typescript_debug`, `other_code_debug` |
| `logic_puzzle` | `ordering`, `deduction`, `modus_ponens`, `modus_tollens`, `other_logic` |
| `code_generation` | `python_generation`, `javascript_generation`, `typescript_generation`, `other_code_generation` |

The sub-intent taxonomy balances dataset coverage and records solver families. It is excluded from the 270M output and feature vector, so regression cannot train on metadata unavailable at inference time.

## Score Anchors

Every score is an integer in `[0, 10]`. Values `1`, `3`, `4`, `6`, `7` and `9` interpolate between the nearest written anchors.

### `deterministic_fit`

| Score | Behavioral anchor | Example |
|---:|---|---|
| 0 | No registered mechanical contract applies. | Open-ended historical explanation. |
| 2 | A superficial pattern resembles a solver, but acceptance is unlikely. | Arithmetic words with missing operands. |
| 5 | Part of the task is structured, but semantic judgment remains. | Summary with subjective tone requirements. |
| 8 | A registered solver likely accepts the untouched input. | Clear proportional-rate word problem. |
| 10 | Exact transformation is mechanically provable. | `Return only the number: 17 + 25`. |

### `reasoning_demand`

| Score | Behavioral anchor | Example |
|---:|---|---|
| 0 | Lookup, label or direct transformation. | Single polarity label. |
| 2 | One obvious inference or operation. | Integer addition. |
| 5 | Several dependent steps. | Multi-stage percentage calculation. |
| 8 | Difficult planning, deduction or debugging. | Interacting constraints in a logic puzzle. |
| 10 | Deep, fragile or specialized reasoning. | Novel proof with many dependent lemmas. |

### `knowledge_uncertainty`

| Score | Behavioral anchor | Example |
|---:|---|---|
| 0 | Prompt-contained or universally stable information. | Extract names from supplied text. |
| 2 | Stable general knowledge. | Capital of Canada. |
| 5 | Domain knowledge with meaningful ambiguity. | Diagnose a framework-specific bug. |
| 8 | Current, external or source-dependent information. | Current office holder. |
| 10 | Correctness cannot be verified from available context. | Ask about an inaccessible private document. |

### `generation_demand`

| Score | Behavioral anchor | Example |
|---:|---|---|
| 0 | One label or token. | `positive`. |
| 2 | Short factual response. | One city name. |
| 5 | Paragraph or small code fragment. | Explain a short bug fix. |
| 8 | Substantial structured text or code. | Complete module with tests. |
| 10 | Long, multi-part generation. | Multi-file application specification. |

### `format_complexity`

| Score | Behavioral anchor | Example |
|---:|---|---|
| 0 | Unconstrained prose. | Explain freely. |
| 2 | Simple short-answer constraint. | Return only the city. |
| 5 | Multiple formatting constraints. | Three bullets under ten words each. |
| 8 | Strict exact-match schema. | Valid JSON with required fields. |
| 10 | Fragile nested or multi-artifact output. | Nested schema plus cross-field invariants. |

## Structural Features

Code, not a model, computes:

- `input_tokens`: tokenizer count when available; deterministic conservative approximation otherwise;
- `requested_output_shape`: one of `free_text`, `short_text`, `number`, `boolean`, `json`, `code`, `list`;
- `deadline_remaining_ms`: clamped non-negative runtime budget.

Output-shape detection is intentionally mechanical and versioned with the feature builder. It is evidence, not a final route.

## Canonical Feature Vector

Feature schema: `feature-vector-v1`.

The exact order is:

1. one-hot intents in `Intent` declaration order;
2. five assessment scores divided by `10`;
3. `log1p(input_tokens) / log1p(8192)`, clamped to `1`;
4. one-hot requested output shapes in enum order;
5. `deadline_remaining_ms / 600000`, clamped to `1`;
6. one-hot solver hints in registered solver order.

The serialized vector stores parallel `names` and `values` arrays. This prevents JSON key sorting from changing matrix column order.

## Solver Hints

Every `SolverRegistration` declares its `(intent, sub_intent)` capabilities for dataset lineage, but runtime hints are conservatively generated by top-level intent. There is no second routing table to drift.

A hint never grants execution. The selected solver receives the original untouched `TaskEnvelope`, runs its own strict acceptance logic and may refuse. A refusal must fall back safely.

## Engine Outcomes

Outcome schema: `engine-outcome-v1`.

Each observed `task x engine` row records:

- correctness;
- latency in milliseconds;
- Fireworks prompt and completion tokens;
- runtime failure;
- peak memory in MB;
- feature, engine and model versions.

Deterministic and E2B rows must contain zero Fireworks tokens. A runtime failure cannot be marked correct. These invariants are enforced by the immutable Python contract before a row reaches regression training.

## Model-Independent Interfaces

The runtime defines four protocols:

- `AssessmentProvider`;
- `OutcomePredictor`;
- `EngineSelector`;
- `EngineExecutor`.

Implementations can change across Sprints 46–48 without changing the evaluator adapters or final output contract.

## Fail-Closed Parsing

The parser accepts only one raw JSON object or an equivalent in-memory mapping. It performs no markdown stripping and no best-effort repair. Invalid JSON, missing fields, additional fields, unknown intents, booleans disguised as integers and out-of-range scores all yield:

```json
{
  "engine": "fireworks",
  "reason": "invalid_task_assessment",
  "feasible_engines": ["fireworks"],
  "safe_fallback": true
}
```

This is a code-owned decision, never model output.

## Trace

Every active three-route decision emits `routing-trace-v1` with:

- task id;
- accepted assessment or `null`;
- canonical features or `null`;
- versioned engine predictions;
- final code-owned decision;
- fallback reason.

The trained assessment and regression artifacts are promoted and embedded in `v3.3.0-full-hybrid`. If any pinned artifact is missing or fails its hash/schema check, `ROUTER_MODE=three_route` enters Fireworks-safe mode and records why. Retired M1/M2A/M2B modes require `ENABLE_LEGACY_CASCADE_MODES=1` and exist only for historical regression tests.

## Verification

```bash
python3 -m unittest tests.test_assessment_contracts
```

The Sprint 45 gate additionally requires the complete repository suite to remain green.
