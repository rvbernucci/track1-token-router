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

Goal: train FunctionGemma and benchmark the local E2B text-only runtime.

Primary runbooks:

- `docs/RUNBOOK_AMD_DIGITALOCEAN.md`
- `docs/RUNBOOK_GEMMA.md`
- `docs/FUNCTIONGEMMA_270M_AMD_TRAINING_TUTORIAL.md`
- `docs/GEMMA_E2B_TEXT_ONLY_RUNTIME.md`

Profiles:

- `runtime-profiles/functiongemma-router.env.example`
- `runtime-profiles/gemma-e2b-text-only.env.example`
- `runtime-profiles/three-route.env.example`

```bash
cp runtime-profiles/three-route.env.example .env.three-route
set -a
. ./.env.three-route
set +a
/opt/venv/bin/python scripts/amd_pod_doctor.py --json
```

Validation:

- FunctionGemma training artifact is persisted privately.
- E2B starts on Linux `x86_64` without loading vision/audio.
- Combined FunctionGemma/E2B RSS is measured under 4 GB.
- Logs include route, local latency, peak RSS and fallback reason.
- The GPU pod is shut down when training and artifact upload finish.

## 2. Fireworks

Goal: calibrate the accuracy fallback and cheapest-sufficient allowed model.

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

- Local routes should record zero Fireworks tokens.
- Fireworks routes should record prompt and completion tokens.
- The exact remote model must come from `ALLOWED_MODELS`.
- Matrix/Pareto selection must be recalibrated against the current allowed set.

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
