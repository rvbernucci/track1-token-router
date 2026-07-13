# Sprint 78 - E2B Deterministic Tool Reasoning

## Final Status

**Closed as `retain` on 2026-07-12.** The structured E2B planner, deterministic proof tools, corpus, CUDA/LiteRT arena and fail-closed runner are complete. The route is deliberately disabled because runtime parity and worst-case latency failed promotion gates. The audited `v3.8.2-e2b-contract` image remains the submission rollback.

## Evaluated Architecture

```text
raw prompt
  -> narrow structural prefilter
  -> Gemma E2B versioned tool plan
  -> schema, role, order and provenance validation
  -> deterministic tool and hash-bound proof
  -> independent proof recomputation
  -> mechanical exact-answer rendering
  -> Answer Contract Engine
  -> local release or Fireworks fallback
```

Gemma interprets the task. It never authorizes execution or release. Exact tasks use mechanical rendering; the proposed second E2B rendering call was evaluated and rejected because it adds latency and an ungrounded generation surface without improving an exact answer.

## Safety Contract

- [x] Preserve `task_id` outside inference and send only raw prompt text.
- [x] Require `tool-plan-v2`; reject old versions, wrappers, extra keys and unknown tools.
- [x] Ground every numeric argument in the prompt.
- [x] Ground inventory operations in their stated order.
- [x] Ground recipe fraction, source count, target count and unit price by semantic role.
- [x] Ground comparison direction and requested endpoint for logic plans.
- [x] Require the arithmetic AST to reproduce the explicit prompt expression.
- [x] Bound AST depth, node count, values, operations and output magnitude.
- [x] Reject ambiguity, cycles, disconnected graphs, non-unique endpoints and invalid arithmetic.
- [x] Prohibit Python, shell, imports, files, network calls and arbitrary expressions.
- [x] Fall back to Fireworks on every planner, proof, contract, deadline or runtime failure.
- [x] Release only after independent deterministic proof recomputation.

## CUDA And Exact-Runtime Lab

- [x] Detect RTX 4060 with 8 GB VRAM.
- [x] Build `llama.cpp` for CUDA compute capability 8.9.
- [x] Pin the official Google Gemma 4 E2B IT QAT Q4_0 GGUF.
- [x] Freeze temperature `0`, 64-token reasoning budget and bounded completion length.
- [x] Run the 100-row sealed CUDA arena.
- [x] Run a balanced 25-row replay through the exact embedded LiteRT runtime.
- [x] Compare tool, exact-plan, release and final-answer agreement.
- [x] Investigate disagreement and reject the assumption that GGUF and LiteRT are interchangeable.

Parity result:

| Measure | Agreement |
|---|---:|
| Tool | 15/25 |
| Exact plan | 15/25 |
| Local release | 17/25 |
| Final answer | 17/25 |

The parity gate failed. CUDA remains a research accelerator, not evidence that can authorize the grading runtime.

## Deterministic Tool Layer

- [x] Inventory flow uses exact `Fraction` state transitions.
- [x] Recipe scaling and price use exact `Fraction` arithmetic.
- [x] Calculator uses a bounded JSON AST without `eval`.
- [x] Ordering logic uses a connected, acyclic directed graph with a unique endpoint.
- [x] Every tool emits normalized inputs, intermediate steps, result and SHA-256 proof hash.
- [x] Every proof is independently recomputed before release.
- [x] Divide-by-zero, overflow, impossible percentages, negative inventory and contradictory relations fail closed.
- [x] Python execution is excluded from the tool policy; existing sandbox code remains outside this route.
- [x] Adversarial tests cover invented values, swapped recipe roles, reversed relations, wrong operators, schema smuggling and code execution attempts.

## Evidence-Grounded Rendering

- [x] Define `tool-evidence-v1` with normalized inputs, steps, result and proof hash.
- [x] Prefer deterministic rendering for all supported exact-answer tools.
- [x] Apply Answer Contract v2 before release.
- [x] Reject a second E2B rendering stage for this policy.
- [x] Reject any answer whose plan semantics are not grounded in the original prompt.
- [x] Fall back on empty, truncated, malformed, ambiguous or contract-invalid output.

## Corpus And Evaluation

- [x] Build 500 immutable task lineages.
- [x] Include 100 inventory, 100 recipe, 100 calculator, 100 logic and 100 unsupported controls.
- [x] Label easy, moderate and difficult template variants.
- [x] Split 400 development and 100 sealed rows by lineage.
- [x] Score schema validity, tool choice, exact plan, accepted route, final answer and unsafe false positives separately.
- [x] Audit the deterministic executor on all 500 rows.
- [x] Treat every unsupported execution as a critical failure.

Mechanical audit: `500/500` passed and `0/100` unsupported controls executed.

Sealed CUDA result after strict provenance:

| Family | Tasks | Verified local | Correct verified |
|---|---:|---:|---:|
| Inventory | 20 | 20 | 20 |
| Recipe | 20 | 4 | 4 |
| Calculator | 20 | 2 | 2 |
| Logic | 20 | 14 | 14 |
| Unsupported | 20 | 0 | 20 rejected |

The validator achieved perfect precision on released CUDA answers, but planner coverage and runtime transfer were insufficient.

## Routing And Economics

- [x] Measure CUDA local acceptance, exact LiteRT acceptance and Fireworks fallback behavior.
- [x] Account for planner inference latency despite zero Fireworks tokens.
- [x] Measure potential avoided calls: 40/100 in the CUDA sealed arena.
- [x] Set promotion independently by tool family.
- [x] Require at least 95% observed precision and a 90% Wilson lower bound of 85%.
- [x] Prevent Nash/minimax from expanding a cohort below the accuracy floor.
- [x] Evaluate the worst-case 100-candidate distribution.

No family is promoted. The exact LiteRT mean was `8.081 s/task`, projecting `808.1 s` for 100 eligible tasks, above the 600-second evaluator limit. Consequently the active policy claims zero token savings.

## Runtime And Release

- [x] Implement `ToolAugmentedRunner` with explicit reason codes and fail-closed fallback.
- [x] Add structural prefilter and deadline guard.
- [x] Preserve dynamic Fireworks authorization through the unchanged fallback runner.
- [x] Keep the experimental policy disabled.
- [x] Run the complete offline release check: 740 tests passed, 1 skipped.
- [x] Re-pull and inspect the stable public image as `linux/amd64`.
- [x] Confirm stable digest `sha256:7ae875639a6b13c8ef84514646b1b6e501da4ef8efd448479615f015239313d9`.
- [x] Reject candidate-image construction after earlier parity and time gates failed.
- [x] Preserve the immutable stable tag rather than publishing an evidence-inferior image.

## Artifacts

- [x] `configs/e2b-tool-policy-v1.json`
- [x] `evals/tool-planner-v2/corpus.jsonl`
- [x] `reports/generated/e2b-tool-executor-audit.json`
- [x] `reports/generated/e2b-tool-v2-cuda-sealed.json`
- [x] `reports/generated/e2b-tool-v2-litert-parity.json`
- [x] `reports/generated/e2b-tool-planner-cuda-parity.json`
- [x] `reports/generated/e2b-tool-exact-image-decision.json`
- [x] `reports/public/e2b-deterministic-tool-reasoning.md`
- [x] Unit tests for schemas, provenance, tools, proofs, contracts, runner transitions and artifact hashes.

## Reproduction

```bash
PYTHONPATH=. python3 scripts/generate_tool_planner_eval.py
PYTHONPATH=. python3 scripts/audit_tool_executor.py \
  --output reports/generated/e2b-tool-executor-audit.json
PYTHONPATH=. python3 scripts/compare_tool_planner_runtimes.py \
  --litert reports/generated/e2b-tool-v2-litert-parity.json \
  --cuda reports/generated/e2b-tool-v2-cuda-sealed.json \
  --output reports/generated/e2b-tool-planner-cuda-parity.json
scripts/offline_release_check.sh
```

## Gate Decision

| Gate | Result |
|---|---|
| Unsupported controls execute no tool | Pass |
| Every released answer has recomputable proof | Pass |
| Released-answer precision | Pass on measured rows |
| Positive hypothetical token savings | Pass on CUDA only |
| CUDA/LiteRT release equivalence | **Fail** |
| Worst-case ten-minute runtime | **Fail** |
| Stable public image remains valid | Pass |

## Definition Of Done

- [x] Reproducible CUDA and LiteRT reports exist.
- [x] A sealed end-to-end arena exists.
- [x] A hash-pinned policy records exactly which tools are promoted: none.
- [x] The stable immutable Docker image is the explicit rollback and final selection.
- [x] The Sprint records an evidence-backed `retain` decision.
