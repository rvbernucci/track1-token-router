# Credit Activation Plan

Use this only when AMD Developer Cloud and/or Fireworks credits are available.

The offline release candidate must remain usable without this file being executed.

## 0. Offline gate

```bash
scripts/offline_release_check.sh
python3 scripts/check_runtime_profiles.py
```

Do not activate paid resources if this fails locally.

## 1. AMD Developer Cloud / DigitalOcean

Goal: expose the local model as an OpenAI-compatible endpoint.

Primary runbooks:

- `docs/RUNBOOK_AMD_DIGITALOCEAN.md`
- `docs/RUNBOOK_VLLM_OPENAI.md`
- `docs/RUNBOOK_SGLANG_OPENAI.md`
- `docs/RUNBOOK_GEMMA.md`

Profiles:

- `runtime-profiles/amd-mi300x-vllm.env.example`
- `runtime-profiles/amd-mi300x-sglang.env.example`
- `runtime-profiles/gemma-local.env.example`

```bash
cp runtime-profiles/amd-mi300x-vllm.env.example .env.amd-vllm
set -a
. ./.env.amd-vllm
set +a
python3 -m router ask "What is 6 * 7? Return only the number." --json
```

Validation:

- `ROUTER_MODE=local` returns a free-form M1 answer.
- `ROUTER_MODE=cascade` runs M1 -> M2A -> optional M2B.
- `ROUTER_MODE=competition` runs guardrails, solvers, risk, budget and final validation.
- Logs include `latency_m1_ms`, `latency_m2a_ms`, and `latency_m2b_ms`.
- Paid GPU VM is destroyed when the session ends.

## 2. Fireworks

Goal: enable remote audit only after local escalation.

Primary runbook:

- `docs/RUNBOOK_FIREWORKS.md`

Profile:

- `runtime-profiles/fireworks-serverless.env.example`

```bash
cp runtime-profiles/fireworks-serverless.env.example .env.fireworks
set -a
. ./.env.fireworks
set +a
export FIREWORKS_API_KEY=<set-locally-not-in-git>
python3 -m router ask "What is 2+2?" --json
```

Validation:

- Easy tasks should stay at `m1_approved` with zero remote tokens.
- Escalated tasks should record `remote_tokens`.
- Fireworks output should be compact `approve` or `replace`.
- `FIREWORKS_MAX_TOKENS` should stay small unless a report justifies raising it.

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

## 5. Demo helpers

Native.Builder is allowed only as auxiliary demo/pitch tooling.

Runbook:

- `docs/RUNBOOK_NATIVE_BUILDER.md`
