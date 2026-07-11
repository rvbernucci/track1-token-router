# Sprint 51 - Sandboxed Code Verification

Status: **Completed - promoted on offline executable evidence**

## Objective

Turn code generation and debugging from weak LLM judgments into executable, bounded verification. The local route may answer only when syntax, contract tests and generated properties pass inside an isolated subprocess.

## Thesis

- Parsing proves shape, not behavior.
- Example tests are necessary but insufficient.
- Property-based and metamorphic checks can expose plausible but wrong code.
- Executing untrusted code requires strict process, resource and import boundaries.

## Deliverables

- `CodeTaskContract` schema for language, signature, constraints and expected behavior.
- Python AST policy and import/call denylist.
- Isolated code runner with wall-clock, CPU, memory and output limits.
- Unit-test, property-test and metamorphic-test generators for supported families.
- Debugging verifier that proves the original fails and the candidate passes when fixtures permit.
- Structured `CodeVerificationReport` consumed by the E2B selective gate.
- Adversarial corpus covering infinite loops, filesystem access, subprocesses and test gaming.

## Checklist

### Contract Extraction

- [x] Extract function name, parameters, return expectations and edge cases.
- [x] Reject missing or contradictory specifications.
- [x] Distinguish code-only output from explanation-plus-code contracts.
- [x] Canonicalize fences without changing program semantics.
- [x] Preserve language/version requirements.

### Static Verification

- [x] Parse Python with `ast` before execution.
- [x] Enforce expected function/class signature.
- [x] Reject forbidden imports and dangerous calls.
- [x] Detect module-level side effects.
- [x] Bound source size, AST depth and literal sizes.
- [x] Reject syntax-valid truncation and placeholder bodies.

### Dynamic Verification

- [x] Execute in a fresh subprocess with sanitized environment.
- [x] Disable network and deny writable project paths.
- [x] Enforce CPU, memory, process-count and output limits.
- [x] Run deterministic examples derived from the prompt.
- [x] Run boundary cases: empty, singleton, duplicates, negatives and large values.
- [x] Add Hypothesis-style properties without adding a heavyweight runtime dependency unless justified.
- [x] Require deterministic repeatability across multiple seeds.

### Cross-Validation

- [x] Let E2B generate a candidate independently of the tests.
- [x] Let deterministic templates produce candidates only for exact supported families.
- [x] Use E2B to review requirement coverage, never to override failed execution.
- [x] Escalate candidates whose tests are incomplete or non-discriminating.
- [x] Record which property killed each rejected candidate.

## Metrics

- verified local coverage by code family;
- mutation score of generated tests;
- false-accept rate against seeded bugs;
- timeout/OOM containment rate;
- p50/p95 verification latency;
- peak RSS under 4 GB/2 vCPU;
- Fireworks tokens avoided by verified code answers.

## Promotion Gate

- At least 90% mutation score on supported code families.
- Zero sandbox escapes and zero leaked environment secrets.
- Zero false accepts on the adversarial bug corpus.
- Every released program passes static, example and property gates.
- Batch runtime remains compatible with the ten-minute evaluator limit.

## Completion Contract

- Planned command: `python3 scripts/evaluate_code_verifier.py --check`.
- Versioned artifact: `configs/code-verifier-policy-v1.json`.
- Evidence report: `reports/generated/sandboxed-code-verification.md`.
- Decision record: promote each supported code family independently; unsupported signatures and languages remain Fireworks-only.
- Dependency: can run beside Sprint 50; exports static/dynamic proof features to Sprint 53.

## Anti-Scope

- Do not execute arbitrary dependencies or install packages at evaluation time.
- Do not claim general code correctness from syntax alone.
- Do not generate tests from the candidate implementation itself.
- Do not support every language before Python verification is proven.

## Completion Evidence

- Command: `python3 scripts/generate_code_verifier_holdout.py && python3 scripts/evaluate_code_verifier.py --check`.
- Holdout: 49 independently labeled rows across seven exact Python families, including one frozen real E2B output, 22 seeded bugs and eight sandbox attacks.
- Result: 18/18 correct candidates released, 22/22 mutants killed, 8/8 adversarial programs contained, zero false accepts and zero false rejects.
- Runtime: 30.37 ms p95 verification latency, 13.28 MiB peak worker RSS and 2.14 seconds for the complete holdout on the development machine.
- Evidence: `reports/generated/code-verifier-evaluation.json` and `reports/generated/sandboxed-code-verification.md`.
- Policy: `configs/code-verifier-policy-v1.json` pins both the holdout and verifier hashes; `tests/test_code_verifier.py` fails on evidence drift.

## Promotion Decision

Promote `add`, `square`, `max_list`, `second_largest`, `unique_preserve_order`, `normalize_slug` and `palindrome` only when the exact contract, AST, example, seeded-property and repeatability gates all pass. E2B review is advisory and cannot override execution. Every unsupported language, ambiguous behavior, incomplete test contract or failed check escalates to Fireworks.
