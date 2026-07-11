# Sprint 50 - Proof-Carrying Math And Logic

Status: **Completed and promoted on 2026-07-10**

## Objective

Build deterministic solvers and verifiers that release a zero-token local answer only when the runtime can attach a machine-checkable proof. Prioritize mathematical reasoning and logical deduction, where verification can be substantially stronger than LLM self-evaluation.

## Thesis

- A local LLM is useful for translating natural language into a candidate equation or constraint set.
- The deterministic engine owns arithmetic, constraint solving and proof verification.
- The LLM may review the proof-to-prompt mapping, but it cannot overrule a failed mechanical check.
- Ambiguity, unsupported operators or multiple valid interpretations always escalate to Fireworks.

## Target Architecture

```text
raw prompt
-> FunctionGemma intent + five scores
-> conservative parser candidates
-> deterministic solver/proof
-> E2B independent candidate
-> deterministic candidate verifier
-> agreement + proof + Answer Contract v2
-> local answer | Fireworks
```

## Deliverables

- Versioned `ProofEnvelope` schema with assumptions, normalized expression, result and verification trace.
- Safe arithmetic evaluator using `Decimal`, bounded integers and an AST operator allowlist.
- Solvers for percentages, ratios, projections, unit conversion and multi-step word problems.
- Constraint engine for ordering, assignment, finite-domain puzzles and propositional deduction.
- Independent answer substitution/recalculation verifier.
- Mutation corpus with paraphrases, distractor numbers, contradictory premises and underdetermined problems.
- `reports/generated/math-logic-proof-coverage.json` and public Markdown report.

## Checklist

### Contracts

- [x] Define `ProofEnvelope` with schema version and deterministic serialization.
- [x] Separate extracted assumptions from computed conclusions.
- [x] Record every rejected parse and ambiguity reason.
- [x] Require one unique normalized interpretation before solving.
- [x] Reject unsupported units, currencies and temporal assumptions.

### Mathematics

- [x] Replace binary arithmetic regex dependence with a bounded AST parser.
- [x] Use `Decimal` for money, percentages and rates.
- [x] Add dimensional/unit consistency checks.
- [x] Add inverse verification by substituting the answer into the original equation.
- [x] Add overflow, divide-by-zero and precision policies.
- [x] Require explicit rounding instructions before rounding.
- [x] Reject prompts containing unused numbers unless the parser proves they are distractors.

### Logic

- [x] Represent entities, domains and constraints separately.
- [x] Enumerate all finite solutions under hard size/time limits.
- [x] Release only unique solutions unless the prompt asks for all solutions.
- [x] Produce counterexamples for invalid conclusions.
- [x] Add modus ponens, modus tollens and quantified-syllogism proof traces.
- [x] Detect inconsistent and underdetermined premises.

### Validation

- [x] Compare deterministic and E2B answers after canonicalization.
- [x] Accept deterministic-only answers when the proof is complete.
- [x] Accept E2B answers only when the verifier proves equivalence.
- [x] Escalate every disagreement rather than selecting by confidence language.
- [x] Fuzz numeric punctuation, locales, signs, grouping and scientific notation.

## Metrics

- solver acceptance coverage by sub-intent;
- proof verification success rate;
- released precision and Wilson lower 95% bound;
- ambiguous-parse rejection rate;
- false-positive release count;
- median/p95 CPU time;
- expected Fireworks tokens saved per 100 tasks.

## Promotion Gate

- Zero false-positive releases on adversarial and structure-held-out packs.
- At least 95% released precision with Wilson lower bound above 90% on a fresh local holdout.
- Every released answer has a reproducible proof trace.
- p95 verification below 100 ms for arithmetic and 500 ms for bounded logic.
- No `eval`, shell execution, network access or unbounded search.

## Completion Contract

- Planned command: `python3 scripts/evaluate_proof_carrying_solvers.py --check`.
- Versioned artifact: `configs/proof-verifier-policy-v1.json`.
- Evidence report: `reports/generated/proof-carrying-math-logic.md`.
- Decision record: promote only verifier families that pass every precision and latency gate; record all others as explicit refusals.
- Dependency: consumes Answer Contract Engine v2 and the existing solver registry; produces proof features for Sprint 53.

## Anti-Scope

- Do not ask an LLM to certify arithmetic without mechanical recomputation.
- Do not solve arbitrary symbolic mathematics in this sprint.
- Do not tune against the locked test after inspecting its failures.
- Do not treat agreement between two correlated LLM outputs as proof.

## Completion Evidence

- command: `python3 scripts/evaluate_proof_carrying_solvers.py --check`;
- holdout: `260` lineage-addressed rows, `180` supported and `80` adversarial refusals;
- result: `180/180` correct releases, `0` false positives, `0` false negatives;
- released precision: `100%`; Wilson lower 95%: `97.91%`;
- latency: math p95 `< 0.11 ms`; logic p95 `< 0.12 ms` on the Mac offline runtime;
- static security gate: no dynamic evaluation, shell, filesystem or network primitive;
- focused tests: `tests.test_proof_engine`, `tests.test_solvers`, and `tests.test_answer_contract_engine` passed;
- promoted artifact: `configs/proof-verifier-policy-v1.json` with pinned dataset, engine and evaluation hashes.

## Promotion Decision

Promote the nine proof families in `proof-verifier-policy-v1`. Unsupported or ambiguous tasks remain refusals and must fall through to later adjudication or Fireworks. Mac latency is valid offline evidence only; Sprint 54 must still enforce the official container envelope.
