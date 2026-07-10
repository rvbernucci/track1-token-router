# Evaluator Assumptions

## Purpose

This document maps what can still surprise us after the Participant Guide reveal. The current strategy is to keep `router/core/*` stable and isolate evaluator-specific input/output changes inside `router/adapters/official/`.

## Confirmed By Participant Guide

- Input path: `/input/tasks.json`.
- Output path: `/output/results.json`.
- Input shape: JSON array of `{ "task_id": "...", "prompt": "..." }`.
- Output shape: JSON array of `{ "task_id": "...", "answer": "..." }`.
- Max runtime: 10 minutes.
- Container startup readiness: 60 seconds.
- Per-request response time: under 30 seconds.
- All responses must be in English.
- Docker image must be public and include `linux/amd64`.
- Compressed image size must not exceed 10GB.
- Fireworks calls must use `FIREWORKS_BASE_URL`.
- Allowed model IDs arrive through `ALLOWED_MODELS`.
- Local models and local tokens count as zero for final score.
- Local model answers count fully toward accuracy.
- Accuracy gate happens before token-efficiency ranking.
- Final grading environment is `4 GB` RAM and `2 vCPU`; large local models should not be assumed.

## Assumption Matrix

| Area | Assumption | Impact If Wrong | Mitigation | Local Test |
|---|---|---|---|---|
| input | The evaluator may send plain text through stdin. | The CLI could over-wrap the prompt or emit noisy stdout. | Keep `plain_text` and `scoring_text_batch` adapters. | `tests.test_official_adapters` |
| input | The official guide requires `/input/tasks.json` as a task array. | Missing exact adapter would fail scoring. | Use `lablab_track1` adapter and `submit-track1`. | `tests.test_official_adapters` |
| input | The evaluator may wrap the same tasks under `tasks`, `items`, `questions`, or `data`, or use `id/question/input_text` aliases. | A harmless wrapper change could crash the container before scoring. | `lablab_track1` accepts the official array plus conservative wrapper/field aliases while preserving output as `{task_id, answer}`. | `test_lablab_track1_accepts_enveloped_tasks_and_alias_fields` |
| input | The evaluator may send one JSON object per task. | Parse failure or lost ids can break scoring. | Keep `json_task` and `scoring_json_envelope` adapters. | `scripts/adapter_drill.py --check` |
| input | The evaluator may send JSONL batches. | Batch order, ids or partial failures may drift. | Keep `jsonl_batch` adapter and answer one line per result. | `tests.test_official_adapters` |
| input | The evaluator may include file metadata or inline content. | The router may ignore attachments needed for accuracy. | Normalize files into `TaskEnvelope.files` and inline content into metadata. | `scoring_file_bundle` fixture |
| output | The evaluator may require plain text only. | JSON output would be marked wrong even if answer is correct. | Adapter-specific `format()` owns final output shape. | `plain_text` and `scoring_file_bundle` tests |
| output | The evaluator may require JSON or JSONL with ids. | Missing ids can make answers unmatchable. | Preserve ids through `TaskEnvelope` and `AnswerResult`. | `json_task`, `jsonl_batch`, `scoring_json_envelope` tests |
| scoring | Accuracy is primary and remote token count is secondary. | Over-aggressive local routing can lose accuracy. | Keep battle drill policy score and remote packet accounting. | `scripts/battle_drill.py` |
| scoring | Local model answers count for accuracy while using zero Fireworks tokens. | A strong local path can dominate Fireworks-only routing, but a weak local path can fail the accuracy gate. | E2B failed its frozen gate and is excluded; retain only mechanically proven local solvers. | Sprint 49 championship ablation |
| resources | Final grading environment is `4 GB` RAM and `2 vCPU`; AMD GPU pod is for development unless organizers say otherwise. | Large Gemma models cannot be assumed as local final-container models. | Keep Docker default `ROUTER_MODE=fireworks` and bundle no rejected model artifact. | `docs/TRACK1_FINAL_ENVIRONMENT_STRATEGY.md` |
| scoring | Parse failure may count as a hard failure. | Extra logs on stdout can poison output. | Keep stdout clean and logs in files/stderr only. | CLI and fuzz tests |
| scoring | Per-request time must stay under 30 seconds and total runtime under 10 minutes. | Long cascades can fail even with good answers. | Use `FIREWORKS_TIMEOUT_S=24`, disable automatic retries, keep a `submit-track1` runtime reserve, and run batch stress plus official Docker smoke tests. | `scripts/batch_stress.py --check` |
| environment | The evaluator may run inside a container. | Local paths or undeclared dependencies can fail. | Keep zero-dependency package and Docker path. | CI and release check |
| environment | Network may be blocked except official endpoints. | Runtime provider calls could hang or fail. | Support dry-run and deterministic fallbacks. | `COMPETITION_DRY_RUN=1` tests |
| environment | Secrets arrive through env vars only. | Logging env or credentials would disqualify us. | Secret scan public artifacts and runtime profiles. | `scripts/secret_scan.py` |
| prohibition | Persistent local state may be disallowed. | Cache-dependent answers can be non-reproducible. | Treat each task as stateless unless official rules allow cache. | State machine tests |
| prohibition | Private dashboards and provider logs cannot be submitted. | Public demo could leak sensitive data. | Export only sanitized public reports. | `scripts/export_public_report.py --check` |

## Kickoff Questions

- Does the official harness invoke only container startup, or can it also pass command arguments?
- Is the 30-second response limit measured per task internally or externally by the harness?
- What is the exact accuracy threshold for leaderboard inclusion?
- Are deterministic solvers allowed before model calls?
- Which exact Fireworks model IDs will appear in `ALLOWED_MODELS`?
- Are AMD Developer Cloud local models expected to run in the same container or as a service endpoint?
- Does the final standardized scoring environment provide GPU access for local inference, or only the development pod?
- Is network access restricted to `FIREWORKS_BASE_URL` only?
- Can we write traces/logs to disk, and if yes, are they inspected?

## Decision Rule

At kickoff, first identify the official contract. Then:

1. Add one fixture that mirrors the official input.
2. Add or update one adapter in `router/adapters/official/`.
3. Add one round-trip test for parse and format.
4. Run `python3 scripts/adapter_drill.py --check`.
5. Only change `router/core/*` if `TaskEnvelope` or `AnswerResult` cannot represent the official contract.
