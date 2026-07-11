# Logs

Folder for local execution logs.

## Objective

Keep enough traces to learn the routing policy without contaminating stdout.

## Recommended format

JSONL, one line per task:

```json
{
  "task_id": "abc",
  "route": "deterministic",
  "functiongemma_ms": 12,
  "deterministic_ms": 1,
  "e2b_ms": 0,
  "remote_ms": 0,
  "remote_prompt_tokens": 0,
  "remote_completion_tokens": 0,
  "remote_total_tokens": 0,
  "final_answer": "4"
}
```

## Local report

```bash
python3 scripts/analyze_traces.py --logs "logs/*.jsonl" --report reports/generated/trace-summary.md
```

The report aggregates routes, remote tokens, latency per step, errors, and parsing failures.

## Do not put here

- API keys.
- secrets.
- large files.
- model weights.
- data that the evaluator does not allow to be persisted.
