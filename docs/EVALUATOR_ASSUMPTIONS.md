# Evaluator Assumptions

## Purpose

This document maps what can surprise us when the official Track 1 evaluator is revealed. The current strategy is to keep `router/core/*` stable and isolate evaluator-specific input/output changes inside `router/adapters/official/`.

## Assumption Matrix

| Area | Assumption | Impact If Wrong | Mitigation | Local Test |
|---|---|---|---|---|
| input | The evaluator may send plain text through stdin. | The CLI could over-wrap the prompt or emit noisy stdout. | Keep `plain_text` and `scoring_text_batch` adapters. | `tests.test_official_adapters` |
| input | The evaluator may send one JSON object per task. | Parse failure or lost ids can break scoring. | Keep `json_task` and `scoring_json_envelope` adapters. | `scripts/adapter_drill.py --check` |
| input | The evaluator may send JSONL batches. | Batch order, ids or partial failures may drift. | Keep `jsonl_batch` adapter and answer one line per result. | `tests.test_official_adapters` |
| input | The evaluator may include file metadata or inline content. | The router may ignore attachments needed for accuracy. | Normalize files into `TaskEnvelope.files` and inline content into metadata. | `scoring_file_bundle` fixture |
| output | The evaluator may require plain text only. | JSON output would be marked wrong even if answer is correct. | Adapter-specific `format()` owns final output shape. | `plain_text` and `scoring_file_bundle` tests |
| output | The evaluator may require JSON or JSONL with ids. | Missing ids can make answers unmatchable. | Preserve ids through `TaskEnvelope` and `AnswerResult`. | `json_task`, `jsonl_batch`, `scoring_json_envelope` tests |
| scoring | Accuracy is primary and remote token count is secondary. | Over-aggressive local routing can lose accuracy. | Keep battle drill policy score and remote packet accounting. | `scripts/battle_drill.py` |
| scoring | Parse failure may count as a hard failure. | Extra logs on stdout can poison output. | Keep stdout clean and logs in files/stderr only. | CLI and fuzz tests |
| scoring | Latency may become a tie-breaker. | Multi-agent cascade can become too slow. | Measure latency envelope in Sprint 29. | `scripts/adapter_drill.py` plus latency lab |
| environment | The evaluator may run inside a container. | Local paths or undeclared dependencies can fail. | Keep zero-dependency package and Docker path. | CI and release check |
| environment | Network may be blocked except official endpoints. | Runtime provider calls could hang or fail. | Support dry-run and deterministic fallbacks. | `COMPETITION_DRY_RUN=1` tests |
| environment | Secrets arrive through env vars only. | Logging env or credentials would disqualify us. | Secret scan public artifacts and runtime profiles. | `scripts/secret_scan.py` |
| prohibition | Persistent local state may be disallowed. | Cache-dependent answers can be non-reproducible. | Treat each task as stateless unless official rules allow cache. | State machine tests |
| prohibition | Private dashboards and provider logs cannot be submitted. | Public demo could leak sensitive data. | Export only sanitized public reports. | `scripts/export_public_report.py --check` |

## Kickoff Questions

- What exact input format will the evaluator send: stdin, file path, HTTP request, JSONL, archive or mixed mode?
- What exact output format is accepted: plain text, JSON object, JSONL, file artifact or HTTP response?
- Are ids required in the final answer, or does scoring preserve request order?
- Is latency scored directly, used as a cutoff, or ignored?
- Are local model tokens counted, or only remote Fireworks tokens?
- Are deterministic solvers allowed before model calls?
- Can we call Fireworks during scoring, or must all endpoints be predeclared?
- Are AMD Developer Cloud local models expected to run in the same container or as a service endpoint?
- Is network access restricted during final scoring?
- Can we write traces/logs to disk, and if yes, are they inspected?

## Decision Rule

At kickoff, first identify the official contract. Then:

1. Add one fixture that mirrors the official input.
2. Add or update one adapter in `router/adapters/official/`.
3. Add one round-trip test for parse and format.
4. Run `python3 scripts/adapter_drill.py --check`.
5. Only change `router/core/*` if `TaskEnvelope` or `AnswerResult` cannot represent the official contract.
