# Core Runtime

The core runtime implements the evaluator-facing contracts and the championship three-route orchestration.

## Target Components

- `TaskEnvelope`: normalized official input.
- `RouteDecision`: one strict FunctionGemma tool call.
- `DeterministicExecutor`: calls one registered solver and accepts refusal.
- `E2BExecutor`: local text-only generation with fixed budgets.
- `FireworksExecutor`: allowed-model Pareto selection and remote inference.
- `FinalValidator`: output shape and evaluator contract checks.
- `AnswerResult`: final answer, route, latency and token metadata.

## Invariants

- FunctionGemma never writes the user answer.
- A deterministic prediction is not proof; the solver must accept independently.
- E2B cannot select its own context or token budget.
- Fireworks model IDs must belong to `ALLOWED_MODELS`.
- Any local parse, timeout, refusal or validation failure falls back to Fireworks.
- Internal tool calls and metadata never leak into the final answer.
- `stdout` remains evaluator-safe; diagnostics go to structured logs.

## Migration Note

Legacy local generation/verification classes remain temporarily under `router/core` while Sprint 45 replaces their factory wiring and tests. They are not part of the active architecture described in [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md).

