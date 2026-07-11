# Answer Contract Engine

Updated: 2026-07-10

Runtime schema: `answer-contract-v2`

## Purpose

The model never writes `/output/results.json`. It returns an unconstrained candidate string. The runtime infers an answer contract from the original prompt, applies only deterministic and unambiguous transformations, validates the transformed value, and then passes the final string to the official JSON adapter.

```text
task prompt
  -> FunctionGemma five-parameter assessment
  -> routing equation
  -> E2B or Fireworks answer candidate
  -> infer AnswerContract
  -> conservative normalization
  -> mechanical validation
  -> accept or preserve/escalate
  -> {"task_id": "...", "answer": "..."}
```

The outer file contract and the task-specific answer contract are separate. `json.dumps` guarantees the former. The Answer Contract Engine improves the latter but cannot repair incorrect semantics.

## Prompt Isolation

The official adapter separates each input object into two channels:

- `task_id`: engine-owned correlation data, never sent to a model;
- `prompt`: the only task content sent to answer models.

FunctionGemma receives the raw prompt plus its fixed tool schema because its output is the intent and five trained scores. E2B and Fireworks use `raw-prompt-v1`: one user message whose content equals the original prompt byte-for-byte after boundary whitespace normalization. They receive no JSON envelope, ID, scores, route, contract or model-selection metadata.

The runtime preserves input order and requires exact ID/order/cardinality alignment before atomically replacing `/output/results.json`.

## Supported Contracts

| Contract | Safe operations | Rejection examples |
|---|---|---|
| label | canonical case; extract one non-negated allowed label | two labels; negated label; no allowed label |
| JSON | remove one enclosing fence; extract exactly one complete object or array; enforce explicit exact keys; unwrap singleton arrays only for singular scalar keys | malformed value; extra/missing keys; multiple top-level JSON candidates |
| number | extract exactly one numeric literal; normalize grouping separators and leading plus; support decimals and scientific notation | multiple numbers; missing number; percentages whose unit is semantically relevant |
| yes/no | canonical lowercase when exactly one value appears | both values or neither |
| literal echo | recover the literal directly specified by the prompt | natural instructions are never treated as literals |
| code | remove enclosing fence; extract parseable Python or a clearly anchored code block | incomplete Python; no code anchor |
| constrained text | verify exact/max words, sentences and items; remove a preface before an exact bullet list | count mismatch; truncated or degenerate text |
| free text | reject empty, unclosed-fence and repeated-generation corruption | semantic correctness remains unproved |

## Safety Invariants

1. A transformation must have exactly one deterministic interpretation.
2. Validation runs after normalization.
3. Ambiguity preserves the original answer and marks the contract invalid.
4. Mechanical validity is never treated as semantic correctness.
5. Every action and inferred constraint is recorded in `AnswerResult.metadata.answer_contract`.
6. The official adapter remains responsible for the JSON array and exact `task_id` pairing.

## Eight-Category Boundary

| Category | Mechanical guarantee | Deliberately not attempted |
|---|---|---|
| factual knowledge | explicit output shape, corruption checks | fact verification or knowledge correction |
| mathematical reasoning | unique number extraction and canonicalization | choosing between multiple candidate results |
| sentiment | one allowed, non-negated label | sentiment inference when the model gives no unique label |
| summarization | word, sentence and item limits | semantic coverage or truncation to force a limit |
| NER | JSON validity, exact keys and conservative scalar/list normalization | inventing, deleting or relabelling entities |
| code debugging | code-fence removal and Python syntax validation for code-only contracts | proving that the bug is fixed |
| logical reasoning | explicit yes/no, label or scalar shape; corruption checks | changing the conclusion or proof |
| code generation | natural code-request detection, fence removal and Python syntax validation | functional correctness without executing tests |

## Runtime Integration

`submit-track1` calls `finalize_answer_result` for every route immediately before the official adapter serializes `/output/results.json`. E2B's selective gate uses the same contract engine before accepting a zero-token local answer. Fireworks uses a separate safe-repair check during model fallback, preventing an ambiguous candidate from being reduced to an arbitrary first value.

## Historical Audit

Run the deterministic audit without model calls:

```bash
python3 scripts/audit_answer_contract_engine.py \
  --candidates reports/generated/amd-pod-e2b-regression-2000/e2b-candidates-96.jsonl \
  --matrix reports/generated/amd-pod-e2b-regression-2000/e2b-outcome-matrix.jsonl \
  --output reports/generated/answer-contract-engine-audit.json \
  --report reports/generated/answer-contract-engine-audit.md
```

The initial audit found 97 originally format-invalid rows with an actual safe transformation. This is a recovery-candidate count, not an accuracy gain. All changed rows must be re-judged on frozen data, followed by the fresh 240-task holdout.

The Fireworks raw-prompt ablation then produced 240 byte-identical Kimi answers while reducing prompt tokens from 31,143 to 13,383. Accuracy stayed at 75%, total Fireworks tokens fell 51.9%, and the contract engine introduced zero regressions. See [`reports/public/raw-prompt-answer-contract-ablation.md`](../reports/public/raw-prompt-answer-contract-ablation.md).

## Promotion Gate

- zero malformed `/output/results.json` files;
- zero ambiguous transformations released as repairs;
- no accuracy regression on unchanged and changed frozen rows;
- hybrid accuracy non-inferior to the promoted Fireworks baseline;
- no material latency or memory regression;
- full unit, integration and container contract suites pass.
