# Sprint 56 - Canonical Local Inference Lab

Status: **Completed - CPU canonical, ROCm challenger rejected for fitting**

## Objective

Run the frozen FunctionGemma 270M assessor and Gemma 4 E2B answer model over all 2,000 Sprint 55 prompts with the exact local protocol intended for competition. Produce resumable, hash-pinned outputs and a trustworthy CPU resource envelope.

## Canonical Flow

```text
raw prompt -> FunctionGemma assessment
raw prompt -> Gemma E2B raw candidate
```

The two models run independently. FunctionGemma never sees the E2B answer, and E2B never sees the assessment, route, inferred contract, task ID or reference answer.

## Frozen Runtime

- FunctionGemma: Q8 GGUF, pinned artifact and llama.cpp revision.
- Gemma E2B: official LiteRT-LM artifact, pinned revision and SHA-256.
- Prompt protocol: `raw-prompt-v1`.
- Context: 2,048 tokens.
- Maximum E2B completion: 96 tokens.
- Temperature: zero and deterministic seed where supported.
- Canonical execution: Linux `x86_64`, CPU, two threads.
- GPU execution: diagnostic acceleration only until parity is proven.

## Deliverables

- Desktop worker doctor and immutable environment report.
- Pinned download and integrity verification for the E2B artifact.
- Append-only FunctionGemma and E2B prediction ledgers.
- 100-row pilot with runtime extrapolation before the full run.
- CPU/GPU parity experiment on a fixed diagnostic cohort.
- Cold/warm latency, throughput, RSS and failure report.
- Exact one-to-one coverage audit against the Sprint 55 inputs.

## Checklist

### Worker Readiness

- [x] Record OS, kernel, CPU, memory, Docker and GPU driver versions.
- [x] Verify `x86_64` execution and native `linux/amd64` Docker support.
- [x] Verify FunctionGemma artifact size and SHA-256.
- [x] Download E2B with resume support and verify its pinned SHA-256.
- [x] Pin llama.cpp, LiteRT-LM and Python package versions.
- [x] Confirm no runtime model download is needed after preparation.
- [x] Keep all credentials outside source, image layers and reports.

### Pilot

- [x] Run 100 lineage-balanced prompts before the full 2,000.
- [x] Verify FunctionGemma schema validity and five-score bounds.
- [x] Verify E2B receives exactly one raw user prompt.
- [x] Prove the LiteRT 96-unit hard completion cap with an adversarial long-output prompt.
- [x] Measure cold start, warm p50/p95, PSS and two-thread throughput.
- [x] Extrapolate total runtime with a conservative p95 budget.
- [x] Stop before the full run if projected runtime or storage is unsafe.

### Full Inference

- [x] Run FunctionGemma over every task and freeze valid assessments.
- [x] Run E2B once per task and preserve the raw answer byte-for-byte.
- [x] Record model hash, settings, latency, memory and exit status per row.
- [x] Write each completed row atomically before advancing.
- [x] Resume without repeating fsynced successful task/model pairs.
- [x] Quarantine malformed, timed-out or empty outputs explicitly.
- [x] Never normalize answers inside the inference process.

### CPU, GPU And Contention

- [x] Treat CPU two-thread output as canonical for regression labels.
- [x] Compare ROCm and CPU outputs on a common diagnostic population.
- [x] Reject GPU outputs because exact assessment parity did not pass.
- [x] Run a contention diagnostic while the desktop is in normal use.
- [x] Repeat authoritative process PSS measurements with one canonical writer.
- [x] Keep the submitted runtime fully functional without a GPU.

## Completion Evidence

- E2B: 2,000/2,000 raw answers, zero quarantines, p50 `5,567.87 ms`, p95 `10,445.42 ms`.
- FunctionGemma CPU: 1,991 valid assessments plus 10 explicitly quarantined task IDs, `99.55%` schema validity, p50 `856.18 ms`, p95 `1,130.17 ms`.
- Combined peak PSS: `3,582,872 KB`, below the 4 GiB grader limit.
- ROCm challenger: 1,988 valid assessments plus 12 quarantines, p50 `209.75 ms`, p95 `250.24 ms`.
- CPU/ROCm common-valid exact assessment parity: `66.63%`; intent parity: `98.74%`.
- Decision: keep CPU outputs canonical; GPU output is diagnostic only and is excluded from fitting.
- Runtime verifier: `python3 scripts/run_e2b_regression_v2_inference.py --check` passes.

## Metrics

- FunctionGemma schema and intent validity;
- E2B completion coverage and failure classes;
- raw output length and truncation rate;
- cold start and warm p50/p95 latency;
- tasks per minute and projected batch runtime;
- process and combined peak RSS;
- CPU/GPU exact and semantic parity;
- duplicate, missing or repeated task/model pairs.

## Promotion Gate

- 2,000/2,000 FunctionGemma records and 2,000/2,000 E2B outcome records.
- Zero reference-answer access by either model runtime.
- At least 99% FunctionGemma schema validity.
- Zero silent E2B truncation beyond the declared 96-token cap.
- Zero duplicate or conflicting task/model records after resume.
- Combined projected runtime preserves the 570-second competition budget for one evaluator batch.
- Canonical artifacts and runtime implementations are SHA-pinned.

## Completion Contract

- Command: `python3 scripts/run_e2b_regression_v2_inference.py --resume --check`.
- Versioned artifact: `configs/e2b-regression-v2-runtime.json`.
- Evidence report: `reports/generated/e2b-regression-v2-inference.md`.
- Decision record: accept CPU-canonical outputs or reject the runtime before labeling.
- Dependency: consumes frozen Sprint 55 inputs; feeds Sprint 57.

## Anti-Scope

- Do not use the RTX 4060 result as grader latency evidence.
- Do not repair model content during inference.
- Do not rerun only failed answers with more tokens.
- Do not replace the model or quantization after observing labels.
- Do not inspect final-holdout correctness in this sprint.
