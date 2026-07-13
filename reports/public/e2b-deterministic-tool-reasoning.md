# E2B Deterministic Tool Reasoning

## Decision

Sprint 78 is closed as **retain**. The tool-augmented route is implemented and reproducible, but it is disabled in `configs/e2b-tool-policy-v1.json`. The submission remains on the audited `v3.8.2-e2b-contract` image.

## Architecture Evaluated

The experiment sends only the raw task text to Gemma 4 E2B. E2B may return one versioned plan for inventory flow, recipe scaling and cost, bounded arithmetic, or ordering logic. Deterministic code then validates schema, checks every value and semantic role against the prompt, executes an allowlisted tool, creates a hash-bound proof, independently recomputes it, applies the Answer Contract Engine, and either releases the exact answer or falls back to Fireworks.

Python, shell commands, imports, files, network calls, unknown tools, free-form expressions, ambiguous relations and ungrounded arguments cannot execute. Exact-answer tools are rendered mechanically, so a second E2B call was rejected as slower and less safe.

## Corpus And Mechanical Audit

- `500` unique lineages: 100 each for inventory, recipe, calculator, logic and unsupported controls.
- `400` development and `100` sealed rows, split by immutable lineage.
- The deterministic executor reproduced `500/500` expected outcomes.
- It accepted `0/100` unsupported controls.
- Arithmetic uses a bounded AST and exact `Fraction` arithmetic; no `eval` is used.
- Logic requires one connected acyclic graph and a unique requested endpoint.

## Sealed CUDA Result

The official Google Gemma 4 E2B IT QAT Q4_0 GGUF ran on an RTX 4060 with a 64-token reasoning budget. Mechanical provenance was reapplied after inference.

| Family | Tasks | Verified local answers | Correct verified answers |
|---|---:|---:|---:|
| Inventory | 20 | 20 | 20 |
| Recipe | 20 | 4 | 4 |
| Calculator | 20 | 2 | 2 |
| Logic | 20 | 14 | 14 |
| Unsupported controls | 20 | 0 | 20 correctly rejected |

Every released CUDA answer was correct, but coverage was uneven. Mean CUDA latency was `1.554 s` per evaluated task.

## Exact Runtime Parity

A balanced 25-row sample was replayed through the exact embedded LiteRT model. The strict post-plan validator removed semantic role swaps that would otherwise have produced incorrect recipe answers.

- Tool agreement: `15/25`.
- Exact plan agreement: `15/25`.
- Release agreement: `17/25`.
- Final answer agreement: `17/25`.
- Mean LiteRT latency: `8.081 s` per task.
- Unsupported false positives: `0`.

The projected worst-case time for 100 structurally eligible tasks is `808.1 s`, above the official 600-second limit. CUDA measurements therefore cannot authorize a policy for the CPU-only grading runtime.

## Token Economics

The verified route would spend zero Fireworks tokens for accepted local answers. On the CUDA sealed set it could avoid remote calls for 40% of all tasks while preserving correctness after strict validation. Because the exact-runtime parity and deadline gates failed, the promoted policy enables no tool families and claims no submission-time token saving.

## Reproduction

```bash
PYTHONPATH=. python3 scripts/generate_tool_planner_eval.py
PYTHONPATH=. python3 scripts/audit_tool_executor.py \
  --output reports/generated/e2b-tool-executor-audit.json
PYTHONPATH=. python3 scripts/compare_tool_planner_runtimes.py \
  --litert reports/generated/e2b-tool-v2-litert-parity.json \
  --cuda reports/generated/e2b-tool-v2-cuda-sealed.json \
  --output reports/generated/e2b-tool-planner-cuda-parity.json
```

## Promotion Outcome

No tool family is promoted. The code, corpus and reports remain reusable training evidence for a future planner fine-tune, while the championship runtime remains unchanged and fail-closed.
