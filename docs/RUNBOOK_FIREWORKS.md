# Runbook Fireworks Serverless

## Objective

Activate Fireworks as the official secure path for Track 1, using the smallest sufficient allowed model for each task and keeping any local inference within the final envelope.

Recommended profile: `runtime-profiles/fireworks-serverless.env.example`.

## Promoted Policy

The frozen baseline of 571 tasks selected `kimi-k2p7-code` globally. In the held-out test, Kimi obtained `59.58%` conservative accuracy, `75.0%` among binary judgments, and `73,870` tokens. Minimax, matrix regression, and intent policy lost accuracy and used more tokens. E2B saved tokens but lost accuracy in a statistically significant way.

Configure:

```bash
FIREWORKS_CHAMPION_MODEL=accounts/fireworks/models/kimi-k2p7-code
```

This value is only a preference. The runtime calls Kimi only if the ID is in `ALLOWED_MODELS`; otherwise, it uses the fallback selector among the officially allowed models.

Current Track 1 note: local models are a valid scoring strategy. Local responses count toward accuracy and use zero Fireworks tokens. However, the current guide also defines the final environment as `4 GB` RAM and `2 vCPU`; therefore, Fireworks remains the safest official path when there is no proven compact local model within this limit.

LoRA/model fine-tuning note: fine-tuning the router decision is permitted; using a Fireworks LoRA/deployment as a responding model does not enter the main path without explicit confirmation from the evaluator. The operational decision is in [`docs/FIREWORKS_LORA_FINE_TUNING_STRATEGY.md`](./FIREWORKS_LORA_FINE_TUNING_STRATEGY.md).

## Required Variables

- `FIREWORKS_API_KEY`: never commit.
- `ALLOWED_MODELS`: official list injected by the harness; the runtime uses the first model when `FIREWORKS_MODEL` is not defined.
- `FIREWORKS_MODEL`: local override for development.
- `FIREWORKS_BASE_URL`: `https://api.fireworks.ai/inference/v1`.
- `FIREWORKS_SERVICE_TIER`: optional; empty uses Standard, `priority` only for manual fallback.
- `FIREWORKS_CHAMPION_MODEL`: first validated option, conditioned on `ALLOWED_MODELS`.

## Activation

```bash
cp runtime-profiles/fireworks-serverless.env.example .env.fireworks
printf "FIREWORKS_API_KEY=<set locally, not in git>\n" >> .env.fireworks.local
chmod 600 .env.fireworks.local
```

Load in local shell:

```bash
set -a
. ./.env.fireworks
. ./.env.fireworks.local
set +a
```

## Secure Real Smoke

The smoke test uses the same OpenAI-compatible client as the router, never prints `FIREWORKS_API_KEY`, and automatically loads `.env.fireworks` + `.env.fireworks.local` if they exist.

```bash
python3 scripts/fireworks_smoke.py --json
```

With explicit model:

```bash
python3 scripts/fireworks_smoke.py \
  --model accounts/fireworks/models/gemma-4-31b-it \
  --max-tokens 64 \
  --prompt "Answer with exactly one word: ready" \
  --json
```

Expected:

- `ok=true`;
- `model` equal to the tested model;
- `usage.total` populated;
- no keys printed in the terminal.

If Gemma returns `HTTP 404` with `Model not found, inaccessible, and/or not deployed`, the Fireworks key may be valid, but the Gemma model is not yet released for the current account/key. In this case, list the models accessible via the `/models` endpoint and temporarily use a model returned by that list until released by the partner/hackathon.

Models with reasoning may consume few tokens only in `reasoning_content`. For a real smoke test, avoid `--max-tokens 8`; use `--max-tokens 64` or greater to allow a final response in `message.content`.

Result of 2026-07-08:

- `accounts/fireworks/models/gemma-4-31b-it` returned `HTTP 404 Not Found`;
- `accounts/fireworks/models/gemma-4-26b-a4b-it` returned `HTTP 404 Not Found`;
- `accounts/fireworks/models/gemma-4-31b-it-nvfp4` returned `HTTP 404 Not Found`;
- `/models` endpoint returned `HTTP 403 Forbidden` for the current key;
- `accounts/fireworks/models/gpt-oss-20b` in simple smoke returned a response without `message.content`, so do not use simple smoke for `gpt-oss`;
- `accounts/fireworks/models/deepseek-v4-flash` validated connectivity with `usage.total=59`, but did not follow the strict format in the smoke test; quality should be measured by the microbench with validators.
- `accounts/fireworks/models/minimax-m3` and `accounts/fireworks/models/kimi-k2p7-code` worked with the current key and also work when called by short alias via project scripts.

### Reasoning Microbench

On 2026-07-07, a real microtest with the project's Fireworks key showed:

- prompt: `Answer with exactly one word: ready`;
- without reasoning control, `glm-5p1` and `glm-5p2` consumed 88-95 tokens and returned reasoning in `content`;
- with `reasoning_effort=none`, `glm-5p1`, `deepseek-v4-pro`, `kimi-k2p6`, and `glm-5p2` responded in 13-18 total tokens;
- `gpt-oss-120b` rejected `reasoning_effort=none` but accepted `reasoning_effort=low`;
- the `reasoning=disabled` field was rejected by the current endpoint as extra input.

Current implementation:

- `cheap` and `medium` tasks use `reasoning_effort=none` when the model is not `gpt-oss`;
- `gpt-oss` uses `low` also in strong tasks, because the microbench with `medium` generated empty/truncated content with a short budget;
- if the model rejects the parameter, the runner retries the call once without the extra body.

## Pareto Microbench

On 2026-07-07, `scripts/fireworks_microbench.py` ran 36 real calls with 6 models and 6 mechanically validated tasks:

- total estimated cost: `0.00275120` USD;
- `deepseek-v4-flash`: 6/6 valid, cost `0.00011788`, average `1775ms`;
- `minimax-m3`: 6/6 valid, cost `0.00055590`, average `1508ms`;
- `kimi-k2p7-code`: 6/6 valid, cost `0.00112655`, average `1193ms`;
- `gpt-oss-20b`: 4/6 automatically, with empty content failures in strong;
- `gpt-oss-120b`: 4/6 automatically, with empty/truncated content failures in strong;
- `qwen3p7-plus`: 3/6, failing by returning reasoning along with the response when the task required a strict response.

Complementary test with `--reasoning-effort-override low` for `gpt-oss`:

- `gpt-oss-120b`: 6/6 valid, cost `0.00026265`, average `1805ms`;
- `gpt-oss-20b`: 5/6 valid, cost `0.00008870`, average `2436ms`;
- conclusion: `low` is the current safe default for `gpt-oss` with a short `max_tokens`.

Generated reports:

- `reports/generated/fireworks-microbench-report.md`;
- `reports/generated/fireworks-microbench-gpt-low-report.md`.

On 2026-07-08, after receiving Fireworks credits, the full Pareto microbench was repeated with `--max-calls 36 --budget-usd 0.10`:

- calls: `36`;
- valid: `33/36`;
- total tokens: `4835`;
- estimated cost: `0.00281451` USD;
- `deepseek-v4-flash`: 6/6, cost `0.00011788`, average `1699ms`;
- `gpt-oss-20b`: 6/6, cost `0.00012393`, average `1934ms`;
- `gpt-oss-120b`: 6/6, cost `0.00024825`, average `788ms`;
- `minimax-m3`: 6/6, cost `0.00055590`, average `1234ms`;
- `kimi-k2p7-code`: 6/6, cost `0.00112255`, average `1648ms`;
- `qwen3p7-plus`: 3/6, failing by returning reasoning along with the response in strict tasks.

Winners by cost in the minimal dataset of 2026-07-08:

- `formatting`: `deepseek-v4-flash`;
- `classification`: `deepseek-v4-flash`;
- `logic`: `deepseek-v4-flash`;
- `math_reasoning`: `gpt-oss-20b`;
- `code_generation`: `gpt-oss-20b`.

Winners by latency in the same dataset:

- `format_json`, `math_reasoning`, and `logic`: `gpt-oss-120b`;
- `code_generation`: `minimax-m3`;
- `cheap_exact_ack` and `cheap_sentiment`: `kimi-k2p7-code`, but with higher cost than `deepseek-v4-flash`.

Smoke test of the official contract on 2026-07-08:

```bash
ROUTER_MODE=fireworks \
ALLOWED_MODELS=accounts/fireworks/models/deepseek-v4-flash,accounts/fireworks/models/gpt-oss-20b,accounts/fireworks/models/gpt-oss-120b,accounts/fireworks/models/minimax-m3 \
python3 -m router submit-track1 \
  --input fixtures/official/lablab_track1_tasks.json \
  --output reports/generated/fireworks-official-smoke-results.json
```

Result:

- `/output/results.json` valid;
- tarefa de resumo usou Fireworks com `173` tokens remotos;
- tarefa aritmetica `6 * 7` saiu por solver deterministico com `0` tokens remotos;
- final answer: `42`.

## Track 1 ACT II - Official Restricted Pareto

The Track 1 guide shared on 2026-07-08 restricts models to:

- `minimax-m3`;
- `kimi-k2p7-code`;
- `gemma-4-31b-it`;
- `gemma-4-26b-a4b-it`;
- `gemma-4-31b-it-nvfp4`.

The runtime normalizes short aliases to full Fireworks IDs:

- `minimax-m3` -> `accounts/fireworks/models/minimax-m3`;
- `kimi-k2p7-code` -> `accounts/fireworks/models/kimi-k2p7-code`;
- `gemma-4-31b-it` -> `accounts/fireworks/models/gemma-4-31b-it`;
- `gemma-4-26b-a4b-it` -> `accounts/fireworks/models/gemma-4-26b-a4b-it`;
- `gemma-4-31b-it-nvfp4` -> `accounts/fireworks/models/gemma-4-31b-it-nvfp4`.

Allowed smoke on 2026-07-08:

- `minimax-m3`: OK, `162` total tokens in the short smoke;
- `kimi-k2p7-code`: OK, `57` total tokens in the short smoke;
- the three Gemma: `HTTP 404 Not Found` on the current local key.

Benchmark `evals/fireworks-pareto/track1-category-microbench.jsonl`, covering the 8 official categories, with `minimax-m3` and `kimi-k2p7-code`:

- calls: `32`;
- mechanically valid: `29/32`;
- estimated cost: `0.00517850` USD;
- `minimax-m3`: `15/16`, cost `0.00141390`, average latency `1330ms`;
- `kimi-k2p7-code`: `14/16`, cost `0.00376460`, average latency `2008ms`.

Observed failures:

- date/money NER normalized `July 8, 2026` to `2026-07-08` and `$450` to `450`; mechanically failed, but semantically probably acceptable;
- `kimi-k2p7-code` failed in `debug_first_even` by returning explanation along with the response and truncated code;
- global `reasoning_effort=none` reduced cost to `0.00282810` USD, but degraded validity to `28/32`; therefore, do not force `none` on strong tasks.

Historical policy before the frozen baseline:

- initial experiments tested Gemma-first and Minimax-first by domain;
- fallback among allowed models if the chosen model returns a quick API error, 404, or response without `message.content`;
- timeout does not cascade to another model in the same request, because the official envelope requires a response under 30s;
- the larger baseline of Sprint 49 replaced this heuristic and promoted Kimi globally;
- the final Sprint 63 calibration superseded this historical policy: `ROUTER_MODE=three_route` is promoted, with Kimi by default and MiniMax for extraction when authorized.

Complementary calibration of 2026-07-09 with all allowed models is in [`docs/FIREWORKS_TRACK1_ALLOWED_CALIBRATION.md`](./FIREWORKS_TRACK1_ALLOWED_CALIBRATION.md).

LoRA/model fine-tuning as responder remains out of the main path due to regulatory risk, unless the harness explicitly exposes the deployment in `ALLOWED_MODELS`: [`docs/FIREWORKS_LORA_FINE_TUNING_STRATEGY.md`](./FIREWORKS_LORA_FINE_TUNING_STRATEGY.md).

## Serverless vs Batch vs Deployments

Fireworks has three different paths, and they do not mean the same thing for Track 1.

The official hackathon text says that Gemma can be accessed via Fireworks AI and AMD Developer Cloud, without separate sign-up, and that there is a Track 1 prize for Best Use of Gemma via Fireworks. The same text also says to check the restrictions of each track before choosing a model.

### Serverless

Serverless is the path closest to Track 1 scoring: OpenAI-compatible call at `FIREWORKS_BASE_URL` with an allowed model in `ALLOWED_MODELS`.

Use in the project:

- `ROUTER_MODE=fireworks`;
- `python3 -m router submit-track1`;
- select the smallest sufficient model within `ALLOWED_MODELS`.

Serving paths:

- Standard: default, without `service_tier`.
- Priority: `service_tier=priority`; more reliable at peak, but more expensive. Do not use in the happy path of credit savings.
- Fast: not a parameter; it is another model ID, such as `accounts/fireworks/routers/glm-5p2-fast`. Only use if this ID comes in `ALLOWED_MODELS` or in explicit local testing.

Prompt cache:

- Fireworks enables prompt caching by default.
- The router keeps the system prompt static at the beginning and the variable input at the end.
- The runner sends `user=track1-token-router-v1` to provide a hint of session affinity and increase the chance of caching on prompts with a common prefix.
- Do not place timestamps or dynamic data in the system prompt.

### Batch Inference Jobs

Batch is for asynchronous inference on a JSONL dataset. It may show models eligible for batch/on-demand, but it is not the natural path of the official contract `/input/tasks.json` -> `/output/results.json`.

Risks:

- can remain in `pending` if the model is not compatible;
- depends on batch quota;
- should not be assumed as allowed in the final scoring;
- can consume credits without improving the official submission.

Acceptable use:

- offline evaluation;
- generate calibration dataset;
- test prompt/router outside the harness.

### On-demand Deployments

Deployments create dedicated GPUs and allow access to models that do not exist in serverless. The Model Library may show Gemma as `Ready` and `Deploy on Demand`, but this does not mean that `accounts/fireworks/models/<gemma>` works directly on the serverless endpoint.

Example: on 2026-07-07, `accounts/fireworks/models/gemma-4-31b-it` appears in the Model Library as on-demand, but `Serverless: Not supported`. A direct call in `/chat/completions` returns `Model not found, inaccessible, and/or not deployed` as long as there is no custom deployment or specific release.

The official documentation for On-Demand Deployments describes this path as deploying a model on a dedicated resource, with subsequent querying via OpenAI-compatible API using the created deployment. This resolves technical access to the model, but changes the nature of the risk: it shifts from just choosing a serverless model to involving the deployment lifecycle.

Acceptable use:

- demonstrate Best Use of Gemma if the hackathon permits this path;
- calibrate Gemma outside of scoring;
- prototype Gemma-first agent.

Risk for Track 1:

- deployment is charged per GPU-second;
- deployment can continue to generate cost if it remains active;
- deployment ID can be different from the model ID listed in `ALLOWED_MODELS`;
- deployment model may not be in `ALLOWED_MODELS`;
- if it does not pass through the harness's `FIREWORKS_BASE_URL`, it may not count correctly toward the score.
- creating a deployment inside the container may violate the idea of a standardized environment and increase startup time.

Questions that need confirmation before using Gemma On-Demand in scoring:

- will the harness inject serverless IDs or deployment IDs in `ALLOWED_MODELS`?
- do calls to custom deployments count toward token efficiency?
- does cost per GPU-second enter the score, or only Fireworks tokens?
- does the deployment need to exist before submission, or can it be created by the container?
- does using a custom deployment violate any Track 1 restriction?

Operational decision:

- final Track 1: `ALLOWED_MODELS` serverless-first, with fallback among allowed models;
- Gemma serverless released in the harness: activate Gemma-first in cheap/medium language;
- Gemma only via On-Demand: use as research/demo path until explicit confirmation;
- local Gemma 26B/31B in the AMD pod: use for development/calibration/demo, do not assume as final-container runtime;
- never create a deployment automatically in a test script without human approval, as it can incur recurring costs.

## Smoke three-route

This command becomes operational in Sprint 48, with the two local models packaged.

```bash
ROUTER_MODE=three_route \
python3 -m router ask "What is 2+2?" --json
```

Expected for easy task:

- local route;
- `remote_tokens.total=0`.

Controlled escalation test:

```bash
ROUTER_MODE=three_route \
python3 -m router ask "Who is the CEO of AMD today?" --json
```

Expected:

- remote call when the matrix decision-maker chooses Fireworks or a local route fails;
- final Fireworks response in the format requested by the task;
- `remote_tokens` registered.

## Official Mode Without Local Endpoint

The Participant Guide injects Fireworks, not a local endpoint. With the final environment of `4 GB` RAM and `2 vCPU`, this is the official secure path:

```bash
ROUTER_MODE=fireworks \
FIREWORKS_API_KEY=<harness-key> \
FIREWORKS_BASE_URL=<harness-base-url> \
ALLOWED_MODELS=<comma-separated-models> \
python3 -m router submit-track1 --input /input/tasks.json --output /output/results.json
```

In this mode, conservative mechanical validators run before the remote call, and the first model in `ALLOWED_MODELS` is used when `FIREWORKS_MODEL` is empty.

## Budget Guard

Before real benchmark:

```bash
export MAX_REMOTE_TOKENS_PER_TASK=300
export MAX_REMOTE_TOKENS_PER_RUN=6000
```

## What Not To Do

- Do not send all tasks directly to Fireworks without measuring.
- Do not increase `FIREWORKS_MAX_TOKENS` without justification.
- Do not commit `.env.fireworks.local`.
- Do not store the API key in logs or screenshots.
