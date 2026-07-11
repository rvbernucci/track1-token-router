# Sprint 54 - Offline Championship Shadow Runtime

Status: **Completed - offline gate passed; release intentionally blocked**

## Objective

Prove the complete deterministic/E2B/Fireworks routing logic offline using frozen E2B candidates, fake Fireworks, saved judge labels and exact evaluator constraints. Produce a release candidate that can be benchmarked immediately when the AMD notebook returns.

## Shadow Flow

```text
/input/tasks.json
-> FunctionGemma recorded/live-compatible assessment
-> deterministic proof attempt
-> E2B frozen candidate replay
-> local adjudication
-> fake/replayed Fireworks fallback
-> Answer Contract v2
-> atomic /output/results.json
```

## Deliverables

- Shadow runtime adapter for frozen E2B and Fireworks responses.
- Freshly generated, lineage-isolated offline holdout.
- Distribution-mix simulator and token-score estimator.
- Chaos suite for timeout, malformed model output and missing artifacts.
- Static 4 GB/2 vCPU/10-minute Docker contract and pinned live-rehearsal command without bundled large weights.
- Promotion report comparing Fireworks-only, deterministic+Fireworks and verified-local hybrid.
- AMD-return runbook with one-command upload, benchmark and artifact retrieval.

## Checklist

### Fresh Evaluation

- [x] Generate new templates without inspecting outcomes during policy fitting.
- [x] Separate train, validation and final holdout by lineage.
- [x] Include all eight categories and adversarial format variants.
- [x] Include distribution shifts toward sentiment/NER and code/math.
- [x] Freeze hashes before evaluation.
- [x] Keep holdout labels unavailable to routing code.

### Shadow Runtime

- [x] Replay exact frozen FunctionGemma assessments and E2B candidates.
- [x] Replay Fireworks responses with recorded token usage.
- [x] Preserve official task order and IDs.
- [x] Enforce one absolute ten-minute deadline.
- [x] Simulate local-model latency and memory envelopes.
- [x] Produce valid output even when optional local artifacts fail.

### Comparative Ablation

- [x] Fireworks-only baseline.
- [x] Deterministic-solvers then Fireworks.
- [x] E2B regression without deterministic proofs.
- [x] Proof-carrying deterministic plus E2B cross-validation.
- [x] Full cohort-aware binary adjudication.
- [x] Compare accuracy first, then scored Fireworks tokens.

### Chaos And Security

- [x] Missing `ALLOWED_MODELS` fails closed in remote mode.
- [x] Unauthorized model override never reaches the client.
- [x] Malformed E2B/Fireworks output cannot corrupt results JSON.
- [x] Code verifier cannot access network, secrets or project files.
- [x] Timeout reserve still writes one answer per input task.
- [x] Logs contain no API keys, tokens or private prompts beyond configured policy.

### AMD Return Readiness

- [x] Pin all commands, packages, model hashes and expected paths.
- [x] Prepare resumable upload/download manifests.
- [x] Separate “must rerun on AMD” from completed offline evidence.
- [x] Limit the AMD session to quantization, exact-runtime latency/memory and fresh inference.
- [x] Define promotion/rejection thresholds before seeing AMD results.

## Metrics

- conservative accuracy by variant and category;
- Fireworks tokens and local coverage by input mix;
- local released precision/Wilson lower bound;
- total runtime and peak RSS;
- timeout/output-schema failure rate;
- token savings confidence interval by lineage;
- deterministic proof and E2B acceptance contributions.

## Promotion Gate

- Hybrid accuracy clears the declared gate on a fresh holdout.
- Verified-local routing reduces Fireworks tokens with no material accuracy regression.
- Every local release has proof or calibrated adjudication evidence.
- Docker contract, environment variables, 4 GB/2 vCPU and ten-minute limits pass.
- Final policy and artifacts are SHA-pinned and reproducible.

## Completion Contract

- Command: `python3 scripts/offline_shadow_championship.py --check`.
- Versioned artifact: `configs/championship-shadow-policy-v1.json`.
- Evidence report: `reports/generated/offline-shadow-championship.md`.
- Decision record: select one exact runtime variant or retain deterministic+Fireworks; no partial promotion.
- Dependency: consumes Sprint 53 policy and every promoted verifier; produces the one-command AMD-return benchmark plan.

## Anti-Scope

- Do not claim AMD performance from Mac timing.
- Do not download or train large models in this sprint.
- Do not spend submission attempts while the local shadow gate fails.
- Do not promote based only on the synthetic 111-task deterministic microbench.

## Completion Evidence

- Fresh corpus: 240 hash-frozen rows across all eight categories, split into 96 train, 64 validation and 80 final-holdout lineages with labels stored outside runtime inputs.
- Selected runtime: proof-carrying deterministic then Fireworks; 80/80 final answers correct, 40/80 released locally, 100% local precision and Wilson lower 95% of 91.24%.
- Proof invariant: every selected local release contains mechanically validated evidence; no raw deterministic candidate is released directly.
- Token efficiency: Fireworks usage fell from 2,676 to 1,145 tokens, saving 1,531 tokens (57.21%); the lineage bootstrap 95% interval is 1,178-1,889 tokens saved.
- Robustness: balanced, sentiment/NER-heavy and code/math-heavy mixes retained 100% replay accuracy.
- Negative control: unverified E2B regression used only 429 Fireworks tokens but fell to 76.25% accuracy and 71.21% local precision, so it was rejected.
- Chaos: missing environment, unauthorized model, malformed E2B/Fireworks, blocked network import, deadline exhaustion and secret-sentinel checks all passed.
- Official I/O: exit code, exact output shape, task order, atomic write, ten-minute budget and missing-environment fail-closed behavior all passed.
- Docker: static `linux/amd64`, 4 GB, 2 vCPU, 10-minute and 10 GB checks passed; live execution did not run because Docker is unavailable on the development Mac.
- AMD handoff: `configs/amd-return-manifest-v1.json`, `scripts/verify_amd_return_manifest.py` and `docs/AMD_RETURN_RUNBOOK.md` pin source/model hashes, thresholds and resumable return checksums.

## Promotion Decision

Complete the offline sprint and retain the exact proof-carrying deterministic+Fireworks variant. Do not promote unverified or cohort-regression E2B routing, even though it spends fewer tokens. Do not authorize a submission attempt until the live Docker resource gate passes and the Gemma E2B artifact is hash-pinned and freshly validated on AMD; the disabled Sprint 53 policy remains disabled.
