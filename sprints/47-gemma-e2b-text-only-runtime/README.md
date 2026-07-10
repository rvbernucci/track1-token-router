# Sprint 47 - Engine Outcome Matrix

## Objective

Package Gemma 4 E2B text-only and build the empirical task-engine matrix used to train the decision regressions.

## Engines Under Test

- registered deterministic solvers;
- quantized Gemma 4 E2B through LiteRT-LM;
- each currently allowed Fireworks model.

## E2B Runtime Checklist

- [x] Pin the E2B repository revision, exact artifact and SHA-256.
- [x] Download the exact artifact to the AMD pod without evaluator-time access.
- [x] Select LiteRT-LM's demand-loaded multimodal package and text-only runtime path.
- [x] Promote the measured 2048-context, 96-output-token baseline after the initial 1024-context smoke.
- [x] Configure at most two CPU threads.
- [x] Run cold/warm two-core CPU smoke tests on the AMD `x86_64` pod.
- [x] Enforce and adversarially verify the 96-token output cap with `max_completion_tokens`.
- [x] Force the OpenAI server to CPU and reject stock-server GPU latency as grader evidence.
- [x] Complete a 93-task two-thread CPU run at context 2048 with zero failures.
- [x] Reject the Web text-only artifact after 93/93 forced-CPU engine failures.
- [x] Measure a speculative-decoding challenger on long-output tasks.
- [x] Measure cold/warm latency and peak RSS alone and beside FunctionGemma.
- [x] Reject E2B task families that miss accuracy or runtime gates.

## Outcome Dataset Checklist

- [x] Run every calibration task against every feasible engine; record unavailable allowed models explicitly.
- [x] Store FunctionGemma assessment with every E2B answer candidate.
- [x] Store exact correctness, output validity, latency, tokens, failure and memory.
- [x] Add a budget-capped, append-only Fireworks teacher judge with exact model provenance.
- [x] Distinguish solver refusal from solver incorrect output.
- [x] Record Fireworks model ID, pricing snapshot and `ALLOWED_MODELS` revision.
- [x] Prevent train/test leakage by task lineage.
- [x] Produce a long-format `task_id x engine_id` matrix.
- [x] Add missing-data rules for unavailable or timed-out engines.

## Regression Targets

For each engine estimate:

- `P(correct | features, engine)`;
- expected latency;
- expected Fireworks input/output tokens;
- probability of runtime failure;
- expected peak-memory contribution for local engines.

Use logistic calibration for correctness and regularized regression for continuous targets. Compare ridge, logistic and a small nonlinear challenger; promote the simplest accuracy-matched model.

## Deliverables

- reproducible E2B runtime layer;
- engine-outcome dataset;
- fitted coefficient matrices and feature normalizers;
- per-engine residual and uncertainty report;
- approved E2B family allowlist.

Teacher judgments are evidence rows, not unquestioned gold. Run at least two pinned judge models, preserve `uncertain`, and resolve disagreement mechanically or with a third independent judge before fitting correctness regressions.

## Gate

The outcome matrix has held-out coverage for all three engine classes, E2B fits the combined 4 GB envelope with safety margin, and regression residuals are bounded well enough for robust decision-making.

## Completion Evidence

- matrix: `651` rows over `93` tasks and seven alternatives, with `227` binary outcomes and `424` explicit missing/refusal/disagreement outcomes;
- independent judge policy: Minimax answers use Claude + Gemini, Kimi answers use Minimax + Gemini, and E2B uses Minimax + Kimi;
- deterministic engine: all 93 open-domain calibration tasks were safely refused after false-positive hardening; accepted solver behavior remains mechanically validated on the separate 111-task solver coverage pack;
- leakage control: five-fold validation is grouped by `mutation_lineage`;
- local memory: FunctionGemma + E2B summed VmHWM is `2.649 GiB`, leaving `1,383.074 MiB` to 4 GiB before final Docker enforcement;
- E2B accuracy: `15/75` binary outcomes correct; held-out model selection preferred a constant `0.20` probability over linear/nonlinear feature models;
- promotion: no E2B intent family is enabled by default; `configs/e2b-route-policy-v1.json` keeps it as an evidence-backed challenger only;
- token ladder: seven genuine 96 -> 192 recoveries and eight genuine 192 -> 384 recoveries, with three judge-only flips excluded from marginal-benefit fitting.

Sprint status: **completed**. The next sprint consumes the pinned outcome coefficients and cannot silently enable E2B.
