# Sprints

## Active Championship Sequence

The architecture reset starts at Sprint 45. These sprints are sequential and all finish with executable evidence.

- [x] [Sprint 45 - Assessment And Decision Contracts](./45-three-route-architecture-migration/README.md)
- [x] [Sprint 46 - FunctionGemma Assessment Training](./46-functiongemma-router-training/README.md)
- [x] [Sprint 47 - Engine Outcome Matrix](./47-gemma-e2b-text-only-runtime/README.md)
- [x] [Sprint 48 - Regression And Game-Theory Decision Engine](./48-three-route-orchestration/README.md)
- [x] [Sprint 49 - Championship Calibration](./49-championship-calibration/README.md)

## Active Offline Competitiveness Sequence

Sprints 50-54 require no AMD notebook. They convert deterministic solvers into proof-carrying validators, fuse them with E2B conservatively and prepare an exact shadow championship runtime.

- [x] [Sprint 50 - Proof-Carrying Math And Logic](./50-proof-carrying-math-logic/README.md)
- [x] [Sprint 51 - Sandboxed Code Verification](./51-sandboxed-code-verification/README.md)
- [x] [Sprint 52 - Grounded Extraction And Classification](./52-grounded-extraction-validation/README.md)
- [x] [Sprint 53 - Bidirectional Local Adjudication](./53-bidirectional-local-adjudication/README.md)
- [x] [Sprint 54 - Offline Championship Shadow Runtime](./54-offline-championship-shadow-runtime/README.md)

## Active E2B Recalibration Sequence

Sprints 55-59 recalibrate E2B from a new 2,000-task corpus. They separate pre-inference probe value from post-answer release safety, use the native `x86_64` desktop as the canonical Docker worker and keep the final 400-row holdout sealed until one exact policy candidate exists.

- [x] [Sprint 55 - E2B Regression V2 Corpus](./55-e2b-regression-v2-corpus/README.md)
- [x] [Sprint 56 - Canonical Local Inference Lab](./56-canonical-local-inference-lab/README.md)
- [x] [Sprint 57 - Ground Truth And Contract Adjudication](./57-ground-truth-and-contract-adjudication/README.md)
- [x] [Sprint 58 - Robust Two-Stage Regression V2](./58-robust-two-stage-regression-v2/README.md)
- [x] [Sprint 59 - Championship Runtime Promotion](./59-championship-runtime-promotion/README.md)

## Final Hybrid Validation Sequence

Sprints 60-64 validate the exact public hybrid image rather than a source-tree approximation. They use the remaining AMD notebook window and a bounded Fireworks budget to prove real local inference, exercise every route, measure the ten-minute batch envelope, calibrate the Pareto frontier and publish one final auditable release decision.

- [x] [Sprint 60 - Exact-Image Local Inference Proof](./60-exact-image-local-inference-proof/README.md)
- [x] [Sprint 61 - Three-Route Failure And Contract Drill](./61-three-route-failure-contract-drill/README.md)
- [x] [Sprint 62 - Eight-Category Ten-Minute Arena](./62-eight-category-ten-minute-arena/README.md)
- [x] [Sprint 63 - Fireworks Pareto Threshold Calibration](./63-fireworks-pareto-threshold-calibration/README.md)
- [x] [Sprint 64 - Final Hybrid Promotion And Submission Lock](./64-final-hybrid-promotion-submission-lock/README.md)

## Completed Foundation

## Parallel Championship Improvement Sequence

Sprints 76 and 77 run concurrently against separate ownership boundaries. Sprint 76 improves the authorized Fireworks fallback with a 1,600-call paired arena over 800 balanced prompts; Sprint 77 recalibrates selective zero-token routing using the complete local evidence without reading the remote arena's sealed audit.

- [x] [Sprint 76 - Fireworks 800-Prompt Champion Arena](./76-fireworks-400-prompt-champion-arena/README.md) - closed as retain; promotion gates failed.
- [x] [Sprint 77 - Local Router ML Recalibration](./77-local-router-ml-recalibration/README.md) - closed as retain; neural candidates remained outside runtime.

## Tool-Augmented Local Reasoning Sequence

Sprint 78 evaluates a new zero-Fireworks-token path in which Gemma E2B creates a constrained plan and deterministic code validates, proves, executes and renders exact answers. A second E2B rendering call was rejected as unnecessary. The path remains experimental unless it passes sealed accuracy, safety, latency and exact-image gates.

- [x] [Sprint 78 - E2B Deterministic Tool Reasoning](./78-e2b-deterministic-tool-reasoning/README.md) - closed as retain; exact-runtime parity and worst-case latency gates failed.
- [x] [Sprint 79 - Dual FunctionGemma Tool Planning](./79-dual-functiongemma-tool-planning/README.md) - complete; promoted public dual-FunctionGemma image with sealed, AMD, clean-pull and harness evidence.
- [ ] [Sprint 80 - Planner Gate Championship](./80-planner-gate-championship/README.md) - three-hour AMD timebox to fit and seal a planner-admission gate over the reconciled full population.

## Post-Submission Robustness Sequence

Sprints 65-69 attack the largest remaining uncertainty: routing accuracy under unseen prompts and shifted evaluator distributions. They are sequential so that E2B safety is established before remote-policy expansion, live integration, contract fuzzing and distribution economics.

- [ ] [Sprint 65 - Adversarial E2B Boundary Audit](./65-adversarial-e2b-boundary-audit/README.md)
- [ ] [Sprint 66 - Expanded Fireworks Pareto Arena](./66-expanded-fireworks-pareto-arena/README.md)
- [ ] [Sprint 67 - Live Three-Route End-to-End Arena](./67-live-three-route-end-to-end-arena/README.md)
- [ ] [Sprint 68 - Answer Contract Adversarial Fuzzing](./68-answer-contract-adversarial-fuzzing/README.md)
- [ ] [Sprint 69 - Distribution Shift And Token Economics](./69-distribution-shift-token-economics/README.md)

## Completed Foundation

Sprints 01-44 produced reusable infrastructure: CLI contracts, adapters, tests, deterministic solvers, Fireworks integration, Pareto/game-theory selection, eval packs, observability, Docker and release automation.

The detailed retired-cascade sprint documents were removed. Git history preserves the experiment without allowing it to compete with the current specification.

## Rule Of Completion

Every active sprint must end with:

- one executable command;
- one versioned artifact;
- one measurable gate;
- tests for success and failure paths;
- one documented promotion or rejection decision.

## Source Of Truth

- Architecture: [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md)
- Router contract: [`../docs/FUNCTIONGEMMA_ROUTER_SPEC.md`](../docs/FUNCTIONGEMMA_ROUTER_SPEC.md)
- Training: [`../docs/FUNCTIONGEMMA_270M_AMD_TRAINING_TUTORIAL.md`](../docs/FUNCTIONGEMMA_270M_AMD_TRAINING_TUTORIAL.md)
- E2B runtime: [`../docs/GEMMA_E2B_TEXT_ONLY_RUNTIME.md`](../docs/GEMMA_E2B_TEXT_ONLY_RUNTIME.md)
