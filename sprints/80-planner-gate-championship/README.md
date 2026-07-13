# Sprint 80 - Planner Gate Championship

## Status

**Ready to execute.** Three-hour championship timebox. The public `v3.9.0-dual-functiongemma` image is the immutable rollback and must not be overwritten.

## Objective

Use the full available labeled population to learn a separate planner-admission gate that improves zero-Fireworks-token tool coverage without reducing released-answer precision.

```text
raw prompt
  -> frozen FunctionGemma assessment
  -> structural features and existing mechanical hints
  -> planner-admission gate
       -> reject: existing E2B/Fireworks route
       -> admit: frozen FunctionGemma planner
          -> deterministic provenance validation
          -> allowlisted tool execution
          -> recomputable proof
          -> Answer Contract Engine
          -> release or Fireworks fallback
```

The planner gate is not a fourth answer engine and cannot release an answer. It only decides whether paying the local planner latency is worthwhile. Mechanical proof remains the final authority.

## Frozen Baseline

- Public rollback image: `ghcr.io/rvbernucci/track1-token-router:v3.9.0-dual-functiongemma`.
- Public OCI digest: `sha256:86d9661ccff0fc181feb46fe517816f2bbb18b47e6fe4ee1a6aeb45f4575b363`.
- Planner Q8 SHA-256: `ec412795782acd3ed836ac35e058099bfdb1c3218a1ee86aef32905377dbddaf`.
- Planner policy SHA-256: `611dfac1494674e0a423ddda1ddc06ca01d3671afb2660519b5e97a328d97ff4`.
- Existing planner corpus: 2,500 lineage-separated cases.
- Existing broad E2B population: approximately 4,000 cases, reconciled by ID before use.
- AMD baseline: 1,393/1,393 released tool answers correct across 1,750 training cases, zero unsafe controls and 541.57 ms mean latency with eight workers.

## Non-Negotiable Rules

- [ ] Never mutate or overwrite the public rollback tag.
- [ ] Never train on sealed labels or select thresholds on sealed results.
- [ ] Split by root lineage and source before fitting any model.
- [ ] Treat duplicate IDs, missing references and cross-split lineage overlap as fatal.
- [ ] Distinguish `planner correct`, `safe decline` and `unsafe/invalid plan`; do not reduce labels to E2B correctness.
- [ ] Require deterministic proof before every local release regardless of gate probability.
- [ ] Prefer a small exported coefficient/tree artifact; add no training framework to the Docker image.
- [ ] Promote only measured gains against the exact public baseline on identical tasks.

## AMD Maximum-Power Plan

- [ ] Keep one ROCm planner server and one ROCm assessor server loaded simultaneously.
- [ ] Use eight server slots per model while respecting each model's context budget.
- [ ] Run disjoint source/category shards with independent resumable JSONL logs.
- [ ] Pin prompt, model, policy and dataset hashes in every shard manifest.
- [ ] Merge strictly by task ID and reject incomplete or duplicate populations.
- [ ] Re-run failures once in an isolated single-worker lane; never silently drop them.
- [ ] Reserve CPU cores for merge, feature extraction and fitting while GPU inference remains saturated.
- [ ] Record GPU utilization, wall time, mean/p95 latency and throughput.

## Wave 1 - Freeze And Reconcile Population (0-20 Minutes)

- [ ] Inventory all planner-v1 train, validation, calibration and sealed IDs.
- [ ] Inventory E2B regression v1/v2, expansion and final-holdout IDs.
- [ ] Reconcile the historical 3,920/3,991/4,400 counts into one authoritative ledger.
- [ ] Remove duplicate mutations by lineage rather than prompt string alone.
- [ ] Preserve original category, difficulty, source, reference and adjudication provenance.
- [ ] Exclude rows without a trustworthy reference from supervised fitting; retain them for runtime stress only.
- [ ] Freeze development, calibration and sealed partitions before inference.
- [ ] Emit population counts and SHA-256 manifest.

**Gate 80.1:** Complete unique ledger, zero cross-split lineage overlap and every supervised row has a mechanically or independently adjudicated reference.

## Wave 2 - Parallel Assessment And Planner Replay (20-75 Minutes)

- [ ] Run the frozen assessment 270M on every reconciled raw prompt.
- [ ] Record raw intent and all five raw scores before calibration.
- [ ] Compute structural features, output-shape hints and existing deterministic solver hints mechanically.
- [ ] Run the frozen Q8 planner on every row admitted by a broad experimental prefilter.
- [ ] Validate tool name, arguments, provenance and semantic roles mechanically.
- [ ] Execute accepted tools and compare rendered answers with references after Answer Contract normalization.
- [ ] Label each row as `correct_release`, `safe_decline`, `invalid_plan`, `wrong_proof` or `reference_unavailable`.
- [ ] Preserve latency and acceptance reason codes.
- [ ] Merge all worker logs and verify exact population coverage.

**Gate 80.2:** Zero missing supervised rows, zero duplicate IDs and every positive label has a recomputable proof matching the reference.

## Wave 3 - Fit Planner-Admission Candidates (75-115 Minutes)

- [ ] Establish the current structural prefilter as the baseline classifier.
- [ ] Fit regularized logistic regression using assessment, structural and deterministic features.
- [ ] Fit a shallow tree or monotonic rule-list challenger for nonlinear interactions.
- [ ] Fit globally and per supported family only where sample size is sufficient.
- [ ] Use class weighting or precision-constrained threshold search; never optimize raw accuracy alone.
- [ ] Calibrate probabilities on the calibration split only.
- [ ] Measure precision, recall, coverage, false-admission rate, Brier score and expected Fireworks tokens avoided.
- [ ] Calculate Wilson 90% lower bounds for each promoted family.
- [ ] Export deterministic coefficients/rules and feature ordering to a hash-pinned JSON artifact.
- [ ] Reject any candidate that needs scikit-learn, PyTorch or another training dependency at runtime.

**Gate 80.3:** Candidate improves validated coverage over the structural prefilter while maintaining at least 99% observed released-answer precision, zero unsafe controls and at least 85% Wilson lower bound per promoted family.

## Wave 4 - Sealed And Distribution-Shift Arena (115-145 Minutes)

- [ ] Freeze candidate algorithm, coefficients and thresholds before reading sealed outcomes.
- [ ] Run the sealed tool holdout exactly once.
- [ ] Run balanced Track 1 category, math-heavy, logic-heavy, code-heavy and ordinary distributions.
- [ ] Include adversarial near-neighbors designed to trigger the wrong tool.
- [ ] Compare baseline and candidate on identical task order and references.
- [ ] Measure planner calls, proof acceptances, Fireworks fallbacks, tokens avoided, latency and accuracy.
- [ ] Verify that non-tool E2B and Fireworks route decisions remain unchanged.
- [ ] Record an explicit `promote` or `retain` decision without threshold repair after sealed evaluation.

**Gate 80.4:** No accuracy regression, zero unsafe sealed release and a measurable reduction in Fireworks calls or planner latency on at least one realistic distribution.

## Wave 5 - Integration And Exact Image (145-170 Minutes)

- [ ] Integrate only the frozen JSON gate artifact and a dependency-free predictor.
- [ ] Fail closed to the current structural prefilter or Fireworks on malformed features/artifacts.
- [ ] Hash-pin the gate artifact in runtime configuration.
- [ ] Add unit tests for success, threshold boundary, malformed artifact, missing feature and fallback behavior.
- [ ] Run the full repository test suite.
- [ ] Build a new immutable challenger tag; never retag `v3.9.0-dual-functiongemma`.
- [ ] Run 4 GB RAM, 2 vCPU, `linux/amd64`, no-network and read-only/non-root gates.
- [ ] Run the exact 20-case proven-tool batch and three worst-case repetitions.
- [ ] Confirm official input/output completeness and all three embedded model hashes.

**Gate 80.5:** Exact image passes every evaluator gate under 540 seconds with no OOM, missing task, invalid JSON or startup download.

## Wave 6 - Public Release And Submission (170-180 Minutes)

- [ ] Publish through the tag-triggered GitHub Actions release workflow.
- [ ] Remove local image state and pull the public tag from GHCR.
- [ ] Audit public `linux/amd64` manifest, OCI labels, digest and compressed size.
- [ ] Re-run official I/O and harness compatibility on the clean pull.
- [ ] Update README, architecture, Pages and submission copy only with measured claims.
- [ ] Update the lablab.ai Docker reference only after all public gates pass.
- [ ] Preserve the exact rollback image reference and digest in the promotion report.

## Stop Conditions

Immediately retain `v3.9.0-dual-functiongemma` if any condition occurs:

- The authoritative population cannot be reconciled without missing labels or leakage.
- A sealed unsupported control executes a tool.
- Released-answer precision falls below the baseline or below 99% observed.
- Wilson 90% lower bound falls below 85% in a promoted family.
- Coverage improves only on training data.
- The gate changes unrelated E2B or Fireworks decisions.
- Runtime, memory or image reliability regresses.
- Less than 30 minutes remain before the deadline without a fully public, clean-pull-tested challenger.

## Definition Of Done

- [ ] Approximately 6,500 available cases are reconciled or exclusions are explicitly accounted for.
- [ ] Every supervised planner label is backed by a reference and deterministic proof audit.
- [ ] A frozen planner-admission gate beats the structural baseline out of sample without reducing precision.
- [ ] The exact challenger image passes all local and public evaluator gates.
- [ ] Submission documentation names the tested immutable tag and digest.
- [ ] An evidence-backed `promote` or `retain` decision is recorded before the deadline.
