# Credit Activation Plan

Use this only when AMD Developer Cloud and/or Fireworks credits are available.

The offline release candidate must remain usable without this file being executed.

## 1. AMD Developer Cloud

Goal: expose the local model as an OpenAI-compatible endpoint.

```bash
export ROUTER_MODE=cascade
export LOCAL_BASE_URL=http://<amd-host>:8000/v1
export LOCAL_MODEL=<local-model-name>
python3 -m router ask "What is 2+2?"
```

Validation:

- `ROUTER_MODE=local` returns a free-form M1 answer.
- `ROUTER_MODE=cascade` runs M1 -> M2A -> optional M2B.
- Logs include `latency_m1_ms`, `latency_m2a_ms`, and `latency_m2b_ms`.

## 2. Fireworks

Goal: enable remote audit only after local escalation.

```bash
export ROUTER_MODE=hybrid
export FIREWORKS_API_KEY=<fireworks-api-key>
export FIREWORKS_MODEL=accounts/fireworks/models/<model>
python3 -m router ask "What is 2+2?" --json
```

Validation:

- Easy tasks should stay at `m1_approved` with zero remote tokens.
- Escalated tasks should record `remote_tokens`.
- Fireworks output should be compact `approve` or `replace`.

## 3. Benchmark

```bash
python3 -m router eval \
  --jsonl evals/offline/tasks.jsonl \
  --expected evals/offline/expected.jsonl \
  --out reports/generated/real-output.jsonl \
  --report reports/generated/real-report.md
```

Compare policies:

```bash
ROUTER_POLICY=aggressive scripts/offline_release_check.sh
ROUTER_POLICY=balanced scripts/offline_release_check.sh
ROUTER_POLICY=conservative scripts/offline_release_check.sh
```

## 4. Do not commit

- Real `.env`
- API keys
- Cloud instance IPs if private
- Provider dashboards or screenshots with secrets
- Logs containing sensitive prompts
