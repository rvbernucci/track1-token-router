# Fireworks Capability Study

Updated on: 2026-07-09

Main source: [`https://docs.fireworks.ai/llms.txt`](https://docs.fireworks.ai/llms.txt)

Complete map generated at: [`docs/FIREWORKS_DOCS_MAP.md`](./FIREWORKS_DOCS_MAP.md)

## Objective

Understand what Fireworks offers before spending credits or adding complexity to Track 1.

Questions this study needs to answer:

- which Fireworks surfaces can appear in the official scoring;
- which features reduce tokens without reducing accuracy;
- which features only help product/operation, but not the hackathon;
- where fine-tuning is safely permitted;
- where deployment/LoRA can break compatibility with `ALLOWED_MODELS`;
- which docs need to become a test, script, or env profile in the repo.

## Capabilities Map

| Area | What Fireworks does | Track 1 Relevance |
|---|---|---|
| Serverless inference | Chat/completions/responses in OpenAI-compatible endpoint, serving paths, pricing, rate limits, and prompt caching. | Critical. It is the scored path when we use `FIREWORKS_BASE_URL`. |
| Model library | Serverless models, custom models, quantization, and families like Kimi. | Critical. We need to choose the smallest sufficient model. |
| API reference | Chat completions, completions, responses, evaluators, quotas, secrets, rerank. | High. Defines parameters, formats, and endpoints. |
| Guides | Text models, reasoning, tool calling, batch, predicted outputs, embeddings/reranking, error codes. | High. Can reduce tokens or format failures. |
| Structured outputs | JSON schema/custom grammar. | High if the harness accepts parameters; can reduce retries due to invalid JSON. |
| Fine-tuning | SFT, RFT, DPO/ORPO, evaluators, LoRA, managed fine-tuning. | Medium. Router fine-tuning is safe; responder LoRA depends on the harness. |
| Dedicated deployments | On-demand deployments, autoscaling, routers, benchmarking, speculative decoding. | Medium/low for Track 1. Only use if `ALLOWED_MODELS` includes deployment IDs. |
| Batch API | Asynchronous jobs and discount for batch processing. | Low for scoring; useful for offline calibration. |
| SDK/tools | Python, TypeScript, Go, Rust, OpenAI/Anthropic compatibility, firectl. | Medium. Helps with integration, but the final Docker should remain simple. |
| Accounts/billing | Service accounts, usage export, quotas, billing. | Operational. Helps control credit. |
| Ecosystem | FireConnect, IDEs, BYOC, Azure Foundry, observability. | Low for Track 1; good for product later. |

## Recommended Study Order

1. [`getting-started/introduction.md`](https://docs.fireworks.ai/getting-started/introduction.md) for the general overview.
2. [`getting-started/quickstart.md`](https://docs.fireworks.ai/getting-started/quickstart.md) for a minimal serverless call.
3. [`serverless/overview.md`](https://docs.fireworks.ai/serverless/overview.md) for billing, headers, prompt caching, and when to use Serverless.
4. [`serverless/pricing.md`](https://docs.fireworks.ai/serverless/pricing.md) for cost per model.
5. [`serverless/serving-paths.md`](https://docs.fireworks.ai/serverless/serving-paths.md) for Standard/Priority/Fast.
6. [`guides/querying-text-models.md`](https://docs.fireworks.ai/guides/querying-text-models.md) for text parameters.
7. [`guides/reasoning.md`](https://docs.fireworks.ai/guides/reasoning.md) to control reasoning and avoid hidden tokens.
8. [`structured-responses/structured-response-formatting.md`](https://docs.fireworks.ai/structured-responses/structured-response-formatting.md) for strict formats.
9. [`guides/inference-error-codes.md`](https://docs.fireworks.ai/guides/inference-error-codes.md) for robust fallback.
10. [`fine-tuning/managed-finetuning-intro.md`](https://docs.fireworks.ai/fine-tuning/managed-finetuning-intro.md) and [`fine-tuning/deploying-loras.md`](https://docs.fireworks.ai/fine-tuning/deploying-loras.md) for LoRA limits.

## Advantage Hypotheses to Test

### 1. Prompt caching

Possible advantage: static system prompt and small variable payload can reduce cost/latency in repeated calls.

Local test:

- keep system prompt static;
- measure tokens/cost with and without fixed prefix;
- record headers if Fireworks exposes cache hit/miss.

### 2. Reasoning controls

Possible advantage: some models spend tokens on reasoning. Controlling `reasoning_effort` can reduce cost.

We already have local evidence in `docs/RUNBOOK_FIREWORKS.md`: `reasoning_effort=none/low` improves cost in some models, but can break strong models if applied globally.

### 3. Structured outputs

Possible advantage: forcing JSON schema/custom grammar can reduce retries and markdown responses.

Risk:

- if the parameter is not accepted by all allowed models, a fallback without extra body is needed;
- it may increase input tokens.

### 4. Fine-tuned router

Possible advantage: train a small/local classifier to predict routing (`solver`, `cheap`, `strong`, `abstain`) based on the microbenchmarks.

Safe because:

- does not change the responding model;
- no need to call Fireworks;
- reduces the risk of over-routing to an expensive model.

### 5. LoRA responder

Possible advantage: small model with better format-following.

High risk:

- Fireworks LoRA requires on-demand/dedicated deployment;
- the ID may fall outside of `ALLOWED_MODELS`;
- Fireworks tokens still count;
- overhead of unmerged LoRA can worsen latency/throughput.

Current decision: study, but do not use in the main runtime.

### 6. Batch API

Possible advantage: cheap calibration outside of scoring.

Risk:

- does not work for the synchronous contract `/input/tasks.json -> /output/results.json`;
- should not enter the final container.

## Repo Action Items

- maintain `scripts/map_fireworks_docs.py` to update the map when the doc changes;
- use `docs/FIREWORKS_DOCS_MAP.md` as the complete inventory;
- transform critical docs into small experiments before spending credits;
- do not mix product features with the final hackathon path;
- keep final submission serverless/local-compatible and `ALLOWED_MODELS`-first.

## Next Study Round

Priority 1:

- Serverless overview/pricing/serving paths/rate limits;
- text models/reasoning/structured outputs/error codes;
- model library and allowed models for Track 1.

Priority 2:

- router fine-tuning;
- evaluators and datasets;
- prompt caching and predicted outputs.

Priority 3:

- deployments/routers/speculative decoding;
- batch API;
- SDKs/ecosystem.
