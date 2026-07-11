# Sprint 59 - Championship Runtime Promotion

Status: **Completed - V2 rejected, deterministic plus Fireworks image published**

## Objective

Evaluate the single Sprint 58 candidate on the untouched 400-row final holdout, integrate it into the official runtime and prove the complete `linux/amd64` container under the exact 4 GB, 2 vCPU, no-network and ten-minute constraints.

## Candidate Variants

1. Fireworks-only baseline.
2. Proof-carrying deterministic then Fireworks baseline.
3. Proof-carrying deterministic, Stage A E2B probe, hard-verifier release, then Fireworks.
4. Full v2 candidate with every promoted cohort and robust abstention rule.

Accuracy gates are evaluated before token counts. A lower-token variant that loses the accuracy gate is ineligible.

## Deliverables

- One-time final-holdout evaluation with immutable run manifest.
- Accuracy-first ablation and paired token-savings bootstrap.
- Versioned promoted or rejected v2 policy.
- Docker image containing pinned local artifacts with no startup download.
- Exact official `/input/tasks.json` to `/output/results.json` rehearsal.
- Public-safe decision report and reproducible resource evidence.
- AMD-return parity checklist for the notebook when it becomes available.

## Current Worker Baseline

The native `x86_64` desktop completed a diagnostic baseline gate on 2026-07-10 while under normal user load:

- platform: `linux/amd64`;
- limits: 4 GiB memory, 2 vCPU and no network;
- compressed image: 50,192,927 bytes;
- uncompressed image: 125,332,007 bytes;
- process peak RSS: 28.508 MiB;
- official result rows: 2/2, valid and ordered;
- gate result: passed.

This proves the worker and gate script, not the future local-model image. FunctionGemma and E2B must still pass the complete idle and contention rehearsals after they are bundled.

## Checklist

### Final Holdout

- [x] Verify all upstream hashes before unsealing labels.
- [x] Record one immutable candidate policy hash before evaluation.
- [x] Run every variant on the same ordered 400 tasks.
- [x] Preserve raw outputs, routes, evidence and token usage.
- [x] Score every official category separately.
- [x] Count uncertain judge outcomes as incorrect.
- [x] Refuse all threshold or coefficient changes after unsealing.

### Accuracy And Efficiency

- [x] Apply the declared overall accuracy gate first.
- [x] Require no material regression against deterministic plus Fireworks.
- [x] Measure local precision and Wilson lower bound by verifier family.
- [x] Report local coverage separately from correctness.
- [x] Count only `FIREWORKS_BASE_URL` usage as scored remote tokens.
- [x] Bootstrap token savings by lineage.
- [x] Stress balanced, sentiment/NER-heavy and code/math-heavy mixes.

### Docker Runtime

- [x] Publish and inspect a public `linux/amd64` image.
- [x] Exclude rejected FunctionGemma and E2B artifacts from the promoted fallback image.
- [x] Prove the image starts with network disabled.
- [x] Run with `--memory=4g --cpus=2 --network=none`.
- [x] Finish with reserve under the 600-second evaluator limit.
- [x] Keep combined peak RSS at or below 3,584 MiB.
- [x] Produce exit code zero and ordered, valid `results.json`.
- [x] Keep compressed image size below 10 GB.
- [x] Read key, base URL and allowed models only from the harness environment.
- [x] Never call a model absent from runtime `ALLOWED_MODELS`.

### Failure And Chaos

- [x] Remove/corrupt each local artifact and prove Fireworks fallback.
- [x] Inject malformed FunctionGemma and E2B outputs.
- [x] Exhaust the deadline and preserve one answer per task.
- [x] Simulate Fireworks timeout, 429, 503 and malformed JSON.
- [x] Confirm code sandbox cannot access network, secrets or project files.
- [x] Scan logs and image layers for credentials and sealed references.
- [x] Repeat authoritative timing with the desktop idle.

### Promotion And Handoff

- [x] Promote one exact policy and pin every artifact hash.
- [x] Keep v2 disabled when any mandatory gate fails.
- [x] Preserve deterministic plus Fireworks as the release fallback.
- [x] Publish aggregate evidence without final-holdout answers.
- [x] Prepare the same image and command for AMD parity rerun.
- [x] Spend no rate-limited submission attempt before all local gates pass.

## Metrics

- accuracy overall and by all eight categories;
- local release precision, Wilson lower bound and coverage;
- Fireworks input, output and total tokens;
- paired token savings confidence interval;
- cold start, batch runtime and p50/p95 task latency;
- process/cgroup peak RSS and OOM count;
- image platform and compressed bytes;
- timeout, malformed-output and fallback success rates;
- CPU/GPU/AMD parity on the diagnostic cohort.

## Promotion Gate

- Overall accuracy at least the declared competition gate.
- Accuracy regression versus deterministic plus Fireworks no greater than one percentage point.
- Local precision at least 95%, Wilson lower 95% at least 90% and zero verifier-invalid releases.
- Perturbation and score-shift route-flip rates both below 5%.
- Positive lower 95% bound for Fireworks token savings.
- Runtime at most 570 seconds and peak RSS at most 3,584 MiB.
- Valid `linux/amd64` image below 10 GB with no startup network.
- All official I/O, authorization, chaos and secret-scan gates pass.

## Completion Contract

- Command: `python3 scripts/evaluate_e2b_regression_v2_championship.py --final-holdout --check`.
- Docker command: `scripts/docker_resource_gate.sh track1-token-router:e2b-v2 reports/generated/e2b-v2-docker-gate.json`.
- Versioned artifact: `configs/e2b-local-adjudication-v2.json`.
- Evidence report: `reports/generated/e2b-regression-v2-championship.md`.
- Decision record: promote v2 exactly or retain proof-carrying deterministic plus Fireworks.
- Dependency: consumes the single Sprint 58 candidate and completes the recalibration program.

## Anti-Scope

- Do not retrain, relabel or retune after the final holdout opens.
- Do not claim GPU timing as evaluator timing.
- Do not submit an image that needs Hugging Face or Fireworks during startup.
- Do not trade an accuracy failure for token savings.
- Do not enable a partially passing policy globally.

## Completion Evidence

- One-time holdout: all 400 rows evaluated in fixed order across four variants with upstream and candidate hashes verified first.
- Baseline: 400 real Fireworks answers through `FIREWORKS_BASE_URL`; MiniMax empty-content cohorts escalated to allowed Kimi rather than cached or hardcoded answers.
- Judgment: 271 mechanical outcomes and 129 semantic rows judged independently by Antigravity and Codex; disagreement counted as incorrect.
- V2 outcome: three local releases, 100% point precision, 43.85% Wilson lower 95% and token-savings bootstrap lower bound zero.
- Decision: `configs/e2b-local-adjudication-v2.json` remains disabled and pins `retain_deterministic_fireworks`.
- Docker: public `linux/amd64`, 50,481,245 compressed bytes, 28.758 MiB peak RSS, one-second wall time, network disabled and valid ordered output.
- Leakage: `evals` is absent from the image; sealed directories are ignored from Git; image layers contain no credential or sampled final-task identifier.
- Tests: the complete suite passed 594 tests after the explicit Fireworks 429/503/malformed chaos case; one environment-dependent test was skipped.
- Public image: `ghcr.io/rvbernucci/track1-token-router:v2.0.1-e2b-v2`, digest `sha256:c9b66097e6a9aa2aa061a35d328ba529fbf732d71dea01751e53be9dfab27553`.
- Release workflow: GitHub Actions run `29143012652` passed clean-clone tests, resource gate, publish, pull and immutable OCI audit.
- Anonymous audit: GitHub Actions run `29143144891` independently pulled and gated the exact public image.
- Public report: `reports/public/e2b-regression-v2-championship.md` contains aggregate evidence only.

## Final Decision

Reject E2B V2 for the submission image. Retain proof-carrying deterministic solvers followed by the allowed Fireworks router. The exact public image was anonymously pulled, resource-gated and audited against revision `5562ace0f412eb39e0475cec83498d2fb5185fb0` and version `v2.0.1-e2b-v2`.
