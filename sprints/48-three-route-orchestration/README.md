# Sprint 48 - Regression And Game-Theory Decision Engine

## Objective

Convert each FunctionGemma assessment into an execution decision using predicted engine outcomes, an accuracy feasibility gate and minimax regret.

## Decision Flow

```text
TaskAssessment + structural features
-> normalize feature vector
-> predict accuracy/latency/tokens/failure for every engine
-> remove engines below accuracy and resource gates
-> minimize worst-case regret over calibrated score uncertainty
-> deterministic | E2B | Fireworks
-> if Fireworks: Pareto/Nash allowed-model selector
```

## Utility

```text
U(engine) =
  accuracy_reward * P(correct)
  - token_weight * remote_tokens
  - latency_weight * latency
  - failure_weight * P(failure)
```

Accuracy is a hard feasibility constraint before utility optimization. Low token cost cannot compensate for an engine predicted below the accuracy gate.

## Checklist

- [x] Load SHA-pinned coefficients and calibration artifacts without network access.
- [x] Predict correctness, latency, tokens, failures and memory for deterministic, E2B and Fireworks engines.
- [x] Convert held-out correctness into per-region 95% Wilson lower bounds for the accuracy gate.
- [x] Implement hard accuracy/resource gates, worst-case utility and minimax-regret selection.
- [x] Keep engine selection deterministic; do not randomize routes.
- [x] Use the existing Nash/Pareto selector only after choosing the Fireworks engine.
- [x] Require a selected deterministic solver to accept the untouched task.
- [x] Replay broad held-out prompts and eliminate every observed deterministic false-positive acceptance.
- [x] Apply code-owned E2B context and 96-output-token budgets.
- [x] Fall back to Fireworks on assessment parse failure, refusal, timeout or invalid local output.
- [x] Enforce `ALLOWED_MODELS` at the Fireworks boundary.
- [x] Preserve deadline reserve for valid output.
- [x] Propagate one absolute ten-minute batch deadline instead of resetting it per task.
- [x] Predict the same Pareto/Nash Fireworks model that the fallback runner will execute.
- [x] Align Fireworks Pareto dominance, Nash payoff and matrix targets to scored token count rather than API dollar price.
- [x] Add an empirical 95% Wilson accuracy gate before Fireworks token minimization and refit the checked-in weights on the same 183 observations.
- [x] Prohibit Fireworks self-judging through cross-model policy and align judge requests with the proven reasoning options.
- [x] Run exact-runtime Fireworks baselines on all `571` validation/test tasks for Kimi and Minimax.
- [x] Freeze per-intent choices on validation before disclosing the locked test.
- [x] Reject the per-intent candidate after it failed the locked-test `60%` conservative promotion gate.
- [x] Add a SHA-pinned, fail-safe runtime policy loader that cannot call a model outside `ALLOWED_MODELS`.
- [x] Trace features, predictions, feasible set, regret and final decision.
- [x] Add a conservative post-E2B rescue gate for strict-format failures, unclosed fences and repeated-generation loops.
- [x] Add a teacher-consensus audit that separates saved errors from unnecessary escalations.
- [x] Add repeated validation-only learning curves to decide whether more data adds signal or should target uncertain regions.
- [x] Replace the initial 93-task E2B prior with the locked 2,000-task regression evidence.
- [x] Enforce the promotion gate: E2B failed its locked-test lower confidence bound and remains disabled.

## Tests

- coefficient and normalization round-trip;
- monotonic response to each score;
- adversarial uncertainty intervals;
- no feasible local engine;
- deterministic refusal;
- E2B timeout/OOM/invalid shape;
- unavailable Fireworks model;
- deadline exhaustion;
- replay determinism.

The 2,000-task experiment is append-only and resumable: the original split has `1,429` train, `284` validation and `287` locked-test cases; after nine malformed FunctionGemma calls fail closed, the regression subset has `1,422`, `283` and `286`, with no lineage or template-family leakage. Final verification passed `453/453` tests and `scripts/verify.sh` on 2026-07-10.

## Locked-Test Decision

- candidate rows: `1,991` at the fixed 96-token ceiling;
- binary teacher consensus: `1,323`; disagreements: `668`;
- best regression: `logistic_nonlinear`; learning curve plateau: `true`;
- locked-test rows selected for E2B: `88/286`;
- selected accuracy: `51.14%`; Wilson lower 95%: `40.87%`;
- required gate: `60%`; promotion: **rejected**;
- promoted outcome artifact SHA-256: `927a64303501d43f3b509a8f48d397d372c4211f8347890827206e82bda60712`;
- runtime policy: `default_enabled=false`, no approved intents.

The evidence does not justify broad random dataset expansion. Future E2B work, outside the championship route, should target uncertainty and observed failure regions only.

## Fireworks Promotion Decision

- Kimi exact-runtime baseline: `571/571` answered, `147,695` Fireworks tokens.
- Minimax exact-runtime baseline: `570/571` answered, `202,913` Fireworks tokens; one transient TLS failure is retained.
- global validation conservative accuracy: Kimi `58.45%`, Minimax `56.69%`;
- global locked-test conservative accuracy: Kimi `59.58%`, Minimax `50.52%`;
- validation-selected intent policy: `56.10%` locked-test conservative accuracy and `81,474` tokens;
- required promotion gate: `60%`; intent policy: **rejected**;
- candidate artifact: `configs/fireworks-intent-policy-v1.json`, `default_enabled=false`;
- active fallback remains the token-aligned matrix plus Pareto/Nash and strict output retry.

The locked test is used only as a pass/fail promotion gate. It never changes an intent choice or coefficient.

## Gate

Fault injection proves fail-closed behavior, replay reproduces every choice, and held-out regret is lower than direct three-way classification and static-rule baselines.
