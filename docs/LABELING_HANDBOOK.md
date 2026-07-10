# FunctionGemma Assessment Labeling Handbook

Version: `assessment-rubric-v2`
Contract: `task-assessment-v1`
Taxonomy: `track1-sub-intents-v1`

## Labeling Principle

Label the task the user requested, not the answer you expect and not the engine you prefer. Gold dataset rows retain `sub_intent` for balanced coverage and auditability, but the FunctionGemma training target contains only `intent` and five integer scores. It never contains an answer, engine, model, confidence or runtime budget.

Use the lowest anchor supported by evidence. Intermediate values mean genuine interpolation between adjacent anchors. Record rationales outside model-visible training content.

## Intent And Sub-Intent

| Intent | Use when | Sub-intents |
|---|---|---|
| `factual_qa` | The desired output is a fact or fact extracted from supplied context. | `stable_fact`, `current_fact`, `context_qa`, `open_domain_fact` |
| `math_reasoning` | Correctness depends on numeric or symbolic mathematics. | `arithmetic`, `percent_fee_math`, `proportional_rate`, `numeric_compare`, `algebra`, `geometry`, `probability`, `statistics`, `other_math` |
| `sentiment` | The desired output is polarity or sentiment toward an aspect. | `polarity`, `aspect_sentiment` |
| `summarization` | The task compresses supplied content. | `constrained_summary`, `extractive_summary`, `abstractive_summary` |
| `ner` | The task extracts named or typed entities. | `entity_extract`, `typed_entity_extract` |
| `code_debugging` | Existing code must be diagnosed or corrected. | `python_debug`, `javascript_debug`, `typescript_debug`, `other_code_debug` |
| `logic_puzzle` | Correctness depends on formal or natural-language deduction. | `ordering`, `deduction`, `modus_ponens`, `modus_tollens`, `other_logic` |
| `code_generation` | New code is the primary requested artifact. | `python_generation`, `javascript_generation`, `typescript_generation`, `other_code_generation` |

When two categories appear, label the operation that determines the expected answer. A request to summarize code is summarization; a request to repair it is code debugging.

## Score Anchors

### `deterministic_fit`

| Score | Evidence standard |
|---|---|
| 0 | No registered mechanical contract is relevant. |
| 2 | Surface words resemble a solver family, but the task remains semantic. |
| 5 | Inputs are structured, but judgment or unsupported cases remain. |
| 8 | A registered solver probably accepts the untouched task and can mechanically verify its result. |
| 10 | The exact solver contract applies and correctness is mechanically provable. |

Never infer this score from intent alone. Compare the untouched prompt against the generated solver capability manifest. If a solver rejects the prompt or changes its meaning, the score cannot be 8 or 10.

### `reasoning_demand`

| Score | Evidence standard |
|---|---|
| 0 | Lookup, direct label or mechanical transformation. |
| 2 | One obvious dependency or operation. |
| 5 | Several dependent steps with recoverable mistakes. |
| 8 | Difficult planning, deduction or debugging with fragile dependencies. |
| 10 | Deep, specialized or highly fragile reasoning. |

Do not raise reasoning because the prompt is long. Count semantic dependencies, alternatives and proof obligations.

### `knowledge_uncertainty`

| Score | Evidence standard |
|---|---|
| 0 | Everything needed is supplied or mathematically fixed. |
| 2 | Stable, widely established knowledge. |
| 5 | Domain knowledge has meaningful ambiguity or version sensitivity. |
| 8 | Current, external, source-dependent or rapidly changing information. |
| 10 | The requested fact cannot be verified from available context. |

This score measures uncertainty of required knowledge, not model confidence.

### `generation_demand`

| Score | Evidence standard |
|---|---|
| 0 | One label, symbol or token. |
| 2 | Short fact, entity list or sentence. |
| 5 | Paragraph, compact explanation or small code fragment. |
| 8 | Substantial structured prose or code. |
| 10 | Long, multi-part or multi-artifact generation. |

Judge the requested output, not the input length.

### `format_complexity`

| Score | Evidence standard |
|---|---|
| 0 | Unconstrained natural language. |
| 2 | One simple short-answer constraint. |
| 5 | Multiple compatible layout or content constraints. |
| 8 | Strict schema, exact-match or parser-sensitive output. |
| 10 | Fragile nested schema or multiple interdependent artifacts. |

JSON is not automatically 8: a single flat object can be 5, while a nested schema with exact keys and ordering can be 8–10.

## Mechanical Evidence

- Run the registered solver against the untouched task for `deterministic_fit` anchors 8 and 10.
- Derive requested output shape and approximate input length in code; teachers do not label those structural features.
- Validate every label with `TaskAssessment.from_mapping`.
- Preserve boundary pairs that change one dimension while holding the rest approximately constant.
- Reject a label if an injected instruction adds `engine`, `route`, `model_id`, an answer or extra fields.

## Adjudication

1. Require at least two independent provider families.
2. Resolve intent and sub-intent by independent agreement or evidence-backed review.
3. Use the median score after three raters; do not let a proposal author be its sole judge.
4. Record revisions append-only with `supersedes` lineage.
5. Send only unresolved examples to a third rater.
6. Keep hidden-test labels teacher-blind and private.

## Split Safety

No normalized template family or mutation lineage may cross train, validation or hidden test. Related rows form connected components before assignment. Hidden prompts may be exposed for inference only; hidden labels remain separate.

## Reject Conditions

Reject or manually review rows with invalid schema, duplicated content, contradictory intent/sub-intent, unsupported solver claims, missing rationales, provider self-adjudication, leaked credentials, engine selection, answer text or uncertain source lineage.
