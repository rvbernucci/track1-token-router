# Fireworks Docs Map

- official_index: `https://docs.fireworks.ai/llms.txt`
- generated_at: `2026-07-09`
- pages: `256`
- groups: `15`

## Strategic Reading Order

1. `getting-started` for product surface and mental model.
2. `serverless`, `models`, `api-reference` and `guides` for Track 1 runtime calls.
3. `fine-tuning` for router fine-tuning and LoRA boundaries.
4. `deployments` only if the official harness permits deployment IDs.
5. `tools-sdks`, `ecosystem` and `accounts` for integration and operations.

## Fireworks Capability Map

| Capability | Docs groups | Track 1 use |
|---|---|---|
| OpenAI-compatible inference | `serverless`, `api-reference`, `tools-sdks` | Main scored path through `FIREWORKS_BASE_URL` and `ALLOWED_MODELS`. |
| Model routing and selection | `models`, `guides`, `serverless` | Choose cheapest sufficient model after local zero-token gates. |
| Structured outputs and strict formats | `structured-responses`, `api-reference`, `guides` | Reduce invalid JSON/code/number outputs before fallback. |
| Embeddings and reranking | `models`, `api-reference`, `guides` | Useful outside Track 1 unless hidden tasks need retrieval; not default. |
| Fine-tuning and evaluators | `fine-tuning`, `api-reference` | Fine-tune/calibrate router; LoRA responder only if allowed by harness. |
| Dedicated deployments | `deployments`, `fine-tuning` | Useful for product workloads; risky for Track 1 unless `ALLOWED_MODELS` includes deployment IDs. |
| SDK and compatibility layers | `tools-sdks`, `ecosystem` | Make integration easier; keep official Docker path minimal. |
| Billing and governance | `accounts` | Credit control, cost exports, service accounts. |

## Group Summary

| Group | Label | Pages | Track 1 Priority |
|---|---|---:|---|
| `_root` | Root / special pages | 1 | low |
| `accounts` | Accounts, billing, users and access | 5 | low |
| `api-reference` | API reference | 22 | high |
| `deployments` | Dedicated deployments | 7 | medium |
| `ecosystem` | Ecosystem integrations | 16 | low |
| `examples` | Examples | 2 | low |
| `faq-new` | FAQ | 1 | low |
| `fine-tuning` | Fine-tuning, LoRA and evaluators | 54 | medium |
| `fireworks-for-work` | Fireworks for Work | 1 | low |
| `getting-started` | Getting started | 5 | high |
| `guides` | Guides and optimization | 19 | high |
| `models` | Model library and model-specific docs | 4 | critical |
| `serverless` | Serverless inference | 4 | critical |
| `structured-responses` | Structured responses | 1 | low |
| `tools-sdks` | Tools, SDKs and protocol compatibility | 114 | medium |

## Complete Page Inventory

Each link below points to the Fireworks markdown copy-page endpoint for LLM use.

### Root / special pages

| Title | Path | Priority | Description |
|---|---|---|---|
| [Fire Pass Setup](https://docs.fireworks.ai/firepass.md) | `firepass.md` | `low` | Open weight models for personal agentic coding — Fire Pass |

### Accounts, billing, users and access

| Title | Path | Priority | Description |
|---|---|---|---|
| [Exporting Billing Metrics](https://docs.fireworks.ai/accounts/exporting-billing-metrics.md) | `accounts/exporting-billing-metrics.md` | `low` | Export billing and usage metrics for all Fireworks services |
| [Usage & Cost Breakdown](https://docs.fireworks.ai/accounts/exporting-usage-and-costs.md) | `accounts/exporting-usage-and-costs.md` | `low` | Break down usage and rated costs by deployment, model, API key, or custom tags — via firectl or the billingUsage API |
| [Service Accounts](https://docs.fireworks.ai/accounts/service-accounts.md) | `accounts/service-accounts.md` | `low` | How to manage and use service accounts in Fireworks |
| [Custom SSO](https://docs.fireworks.ai/accounts/sso.md) | `accounts/sso.md` | `low` | Set up custom Single Sign-On (SSO) authentication for Fireworks AI |
| [Managing users](https://docs.fireworks.ai/accounts/users.md) | `accounts/users.md` | `low` | Add, delete, and manage roles for users in your Fireworks account |

### API reference

| Title | Path | Priority | Description |
|---|---|---|---|
| [Create a Message](https://docs.fireworks.ai/api-reference/anthropic-messages.md) | `api-reference/anthropic-messages.md` | `high` | **Anthropic-compatible endpoint.** |
| [Create Evaluator](https://docs.fireworks.ai/api-reference/create-evaluator.md) | `api-reference/create-evaluator.md` | `high` | Creates a custom evaluator for scoring model outputs. Evaluators use the [Eval Protocol](https://evalprotocol.io) to define test cases, run model inference, and score responses. They are used with evaluation jobs and Reinforcement Fine-Tuning (RFT). |
| [Delete Evaluator](https://docs.fireworks.ai/api-reference/delete-evaluator.md) | `api-reference/delete-evaluator.md` | `high` | Deletes an evaluator and its associated versions and build artifacts. |
| [Delete Response](https://docs.fireworks.ai/api-reference/delete-response.md) | `api-reference/delete-response.md` | `high` | Deletes a model response by its ID. Once deleted, the response data will be gone immediately and permanently. |
| [Get Evaluator Build Log Endpoint](https://docs.fireworks.ai/api-reference/get-evaluator-build-log-endpoint.md) | `api-reference/get-evaluator-build-log-endpoint.md` | `high` | Returns a signed URL to download the evaluator's build logs. Useful for debugging `BUILD_FAILED` state. |
| [Get Evaluator Source Code Endpoint](https://docs.fireworks.ai/api-reference/get-evaluator-source-code-endpoint.md) | `api-reference/get-evaluator-source-code-endpoint.md` | `high` | Returns a signed URL to download the evaluator's source code archive. Useful for debugging or reviewing the uploaded code. |
| [Get Evaluator Upload Endpoint](https://docs.fireworks.ai/api-reference/get-evaluator-upload-endpoint.md) | `api-reference/get-evaluator-upload-endpoint.md` | `high` | Returns signed URLs for uploading evaluator source code (**step 3** in the [Create Evaluator](/api-reference/create-evaluator) workflow). After receiving the signed URL, upload your `.tar.gz` archive using HTTP `PUT` with `Content-Type: application/octet-stream` header. |
| [Get Evaluator](https://docs.fireworks.ai/api-reference/get-evaluator.md) | `api-reference/get-evaluator.md` | `high` | Retrieves an evaluator by name. Use this to monitor build progress after creation (**step 6** in the [Create Evaluator](/api-reference/create-evaluator) workflow). |
| [Get Quota](https://docs.fireworks.ai/api-reference/get-quota.md) | `api-reference/get-quota.md` | `high` | Gets a single quota by resource name. |
| [Get Secret](https://docs.fireworks.ai/api-reference/get-secret.md) | `api-reference/get-secret.md` | `high` | Retrieves a secret by name. Note that the `value` field is not returned in the response for security reasons. Only the `name` and `key_name` fields are included. |
| [List Evaluators](https://docs.fireworks.ai/api-reference/list-evaluators.md) | `api-reference/list-evaluators.md` | `high` | Lists all evaluators for an account with pagination support. |
| [List Quotas](https://docs.fireworks.ai/api-reference/list-quotas.md) | `api-reference/list-quotas.md` | `high` | Lists all quotas for an account. |
| [List Responses](https://docs.fireworks.ai/api-reference/list-responses.md) | `api-reference/list-responses.md` | `high` | Get a list of all responses for the authenticated account. |
| [List Secrets](https://docs.fireworks.ai/api-reference/list-secrets.md) | `api-reference/list-secrets.md` | `high` | Lists all secrets for an account. Note that the `value` field is not returned in the response for security reasons. Only the `name` and `key_name` fields are included for each secret. |
| [Create Chat Completion](https://docs.fireworks.ai/api-reference/post-chatcompletions.md) | `api-reference/post-chatcompletions.md` | `high` | Create a completion for the provided prompt and parameters. |
| [Create Completion](https://docs.fireworks.ai/api-reference/post-completions.md) | `api-reference/post-completions.md` | `high` | Create a completion for the provided prompt and parameters. |
| [Create Response](https://docs.fireworks.ai/api-reference/post-responses.md) | `api-reference/post-responses.md` | `high` | Creates a model response, optionally interacting with custom tools via the Model Context Protocol (MCP). This endpoint supports conversational continuation and streaming. |
| [Rerank documents](https://docs.fireworks.ai/api-reference/rerank-documents.md) | `api-reference/rerank-documents.md` | `high` | Rerank documents for a query using relevance scoring |
| [Update Evaluator](https://docs.fireworks.ai/api-reference/update-evaluator.md) | `api-reference/update-evaluator.md` | `high` | Updates evaluator metadata (display_name, description, default_dataset). Changing `requirements` or `entry_point` triggers a rebuild. To upload new source code, set `prepare_code_upload: true` then follow the upload flow. |
| [Update Quota](https://docs.fireworks.ai/api-reference/update-quota.md) | `api-reference/update-quota.md` | `high` | Updates a quota. |
| [Upload Dataset Files](https://docs.fireworks.ai/api-reference/upload-dataset-files.md) | `api-reference/upload-dataset-files.md` | `high` | Provides a streamlined way to upload a dataset file in a single API request. This path can handle file sizes up to 150Mb. For larger file sizes use [Get Dataset Upload Endpoint](get-dataset-upload-endpoint). |
| [Validate Evaluator Upload](https://docs.fireworks.ai/api-reference/validate-evaluator-upload.md) | `api-reference/validate-evaluator-upload.md` | `high` | Triggers server-side validation of the uploaded source code (**step 5** in the [Create Evaluator](/api-reference/create-evaluator) workflow). The server extracts and processes the archive, then builds the evaluator environment. Poll [Get Evaluator](/api-reference/get-evaluator) to monitor progress. |

### Dedicated deployments

| Title | Path | Priority | Description |
|---|---|---|---|
| [Autoscaling](https://docs.fireworks.ai/deployments/autoscaling.md) | `deployments/autoscaling.md` | `medium` | Configure how your deployment scales based on traffic |
| [Performance benchmarking](https://docs.fireworks.ai/deployments/benchmarking.md) | `deployments/benchmarking.md` | `medium` | Measure and optimize your deployment's performance with load testing |
| [Client-side performance optimization](https://docs.fireworks.ai/deployments/client-side-performance-optimization.md) | `deployments/client-side-performance-optimization.md` | `medium` | Optimize your client code for maximum performance with dedicated deployments |
| [Exporting Metrics](https://docs.fireworks.ai/deployments/exporting-metrics.md) | `deployments/exporting-metrics.md` | `medium` | Export metrics from your dedicated deployments to your observability stack |
| [Regions](https://docs.fireworks.ai/deployments/regions.md) | `deployments/regions.md` | `medium` | Fireworks runs a global fleet of hardware on which you can deploy your models. |
| [Routers](https://docs.fireworks.ai/deployments/routers.md) | `deployments/routers.md` | `medium` | Distribute traffic across multiple deployments for A/B testing, traffic migration, and load distribution. |
| [Speculative Decoding](https://docs.fireworks.ai/deployments/speculative-decoding.md) | `deployments/speculative-decoding.md` | `medium` | Speed up generation with draft models and n-gram speculation |

### Ecosystem integrations

| Title | Path | Priority | Description |
|---|---|---|---|
| [Claude Code](https://docs.fireworks.ai/ecosystem/fireconnect/claude-code.md) | `ecosystem/fireconnect/claude-code.md` | `low` | Use Fireworks AI models in Claude Code with the FireConnect CLI |
| [Codex](https://docs.fireworks.ai/ecosystem/fireconnect/codex.md) | `ecosystem/fireconnect/codex.md` | `low` | Use Fireworks AI models in OpenAI Codex CLI with the FireConnect CLI |
| [Cursor](https://docs.fireworks.ai/ecosystem/fireconnect/cursor.md) | `ecosystem/fireconnect/cursor.md` | `low` | Use Fireworks AI models in Cursor IDE with the FireConnect CLI |
| [Deep Agents](https://docs.fireworks.ai/ecosystem/fireconnect/deepagents.md) | `ecosystem/fireconnect/deepagents.md` | `low` | Use Fireworks AI models in LangChain Deep Agents Code with the FireConnect CLI |
| [Microsoft Foundry](https://docs.fireworks.ai/ecosystem/fireconnect/microsoft-foundry.md) | `ecosystem/fireconnect/microsoft-foundry.md` | `low` | Route OpenCode, Codex, and Pi through Fireworks models deployed in your Azure subscription with FireConnect |
| [OpenCode](https://docs.fireworks.ai/ecosystem/fireconnect/opencode.md) | `ecosystem/fireconnect/opencode.md` | `low` | Use Fireworks AI models in OpenCode with the FireConnect CLI |
| [Overview](https://docs.fireworks.ai/ecosystem/fireconnect/overview.md) | `ecosystem/fireconnect/overview.md` | `low` | Route Claude Code, OpenCode, Codex, Pi, Cursor, VS Code, and Deep Agents through Fireworks AI or Microsoft Foundry models |
| [Pi](https://docs.fireworks.ai/ecosystem/fireconnect/pi.md) | `ecosystem/fireconnect/pi.md` | `low` | Use Fireworks AI models in Pi with the FireConnect CLI |
| [VS Code](https://docs.fireworks.ai/ecosystem/fireconnect/vscode.md) | `ecosystem/fireconnect/vscode.md` | `low` | Use Fireworks AI models in GitHub Copilot Chat with the FireConnect CLI |
| [Agent Frameworks](https://docs.fireworks.ai/ecosystem/integrations/agent-frameworks.md) | `ecosystem/integrations/agent-frameworks.md` | `low` | Build production-ready AI agents with Fireworks and leading open-source frameworks |
| [Microsoft Foundry](https://docs.fireworks.ai/ecosystem/integrations/azure-foundry.md) | `ecosystem/integrations/azure-foundry.md` | `low` | Deploy frontier open models inside your Azure subscription, billed through Azure. |
| [How Setup Works](https://docs.fireworks.ai/ecosystem/integrations/byoc/how-setup-works.md) | `ecosystem/integrations/byoc/how-setup-works.md` | `low` | Understand the high-level onboarding flow for Bring Your Own Cluster. |
| [Operational Model](https://docs.fireworks.ai/ecosystem/integrations/byoc/operational-model.md) | `ecosystem/integrations/byoc/operational-model.md` | `low` | Learn how Fireworks operates Bring Your Own Cluster environments day to day. |
| [Bring Your Own Cluster](https://docs.fireworks.ai/ecosystem/integrations/byoc/overview.md) | `ecosystem/integrations/byoc/overview.md` | `low` | Run Fireworks inference in your own Kubernetes cluster, cloud account or data center, and network boundary. |
| [Development Setup with Fireworks Docs MCP](https://docs.fireworks.ai/ecosystem/integrations/development-setup.md) | `ecosystem/integrations/development-setup.md` | `low` | Configure the Fireworks AI Docs MCP server for Claude Code and Cursor |
| [MLOps & Observability](https://docs.fireworks.ai/ecosystem/integrations/mlops-observability.md) | `ecosystem/integrations/mlops-observability.md` | `low` | Track and monitor your Fireworks AI deployments with leading MLOps and observability platforms |

### Examples

| Title | Path | Priority | Description |
|---|---|---|---|
| [Cookbooks](https://docs.fireworks.ai/examples/cookbooks.md) | `examples/cookbooks.md` | `low` | Interactive Jupyter notebooks demonstrating advanced use cases and best practices with Fireworks AI |
| [Courses](https://docs.fireworks.ai/examples/introduction.md) | `examples/introduction.md` | `low` | Standalone end-to-end examples showing how to use Fireworks to solve real-world use cases |

### FAQ

| Title | Path | Priority | Description |
|---|---|---|---|
| [How many tokens per image?](https://docs.fireworks.ai/faq-new/billing-pricing/how-many-tokens-per-image.md) | `faq-new/billing-pricing/how-many-tokens-per-image.md` | `low` | Learn how to calculate token usage for images in vision models and understand pricing implications |

### Fine-tuning, LoRA and evaluators

| Title | Path | Priority | Description |
|---|---|---|---|
| [Fireworks Agent: Classification](https://docs.fireworks.ai/fine-tuning/agent/classification.md) | `fine-tuning/agent/classification.md` | `medium` | Benchmark base models, fine-tune on labeled data, and pick the best classifier — automatically. |
| [Fireworks Agent: Preference Learning (DPO/ORPO)](https://docs.fireworks.ai/fine-tuning/agent/dpo.md) | `fine-tuning/agent/dpo.md` | `medium` | Run preference fine-tuning end-to-end with optional base-model sweep, automatic pair generation, and pairwise evaluation. |
| [Fireworks Agent: Evaluator Authoring](https://docs.fireworks.ai/fine-tuning/agent/evaluators.md) | `fine-tuning/agent/evaluators.md` | `medium` | Have Fireworks Agent generate a reusable evaluator from your dataset — for scoring candidates in an SFT sweep, or for use with Managed RFT. |
| [Fireworks Agent Overview](https://docs.fireworks.ai/fine-tuning/agent/introduction.md) | `fine-tuning/agent/introduction.md` | `medium` | Describe what you want, approve the plan and cost, get a deployed fine-tuned model. |
| [Fireworks Agent: Supervised Fine-Tuning](https://docs.fireworks.ai/fine-tuning/agent/sft.md) | `fine-tuning/agent/sft.md` | `medium` | Run end-to-end SFT with Fireworks Agent — dataset inspection, hyperparameter sweep, evaluator-guided selection, and a deployed winner. |
| [Use Fireworks Agent with Claude Code, Cursor, Codex, and other coding agents](https://docs.fireworks.ai/fine-tuning/agent/use-with-coding-agents.md) | `fine-tuning/agent/use-with-coding-agents.md` | `medium` | Install the Fireworks Agent skill file once and drive end-to-end fine-tuning from your coding agent. |
| [Training Overview](https://docs.fireworks.ai/fine-tuning/cli-reference.md) | `fine-tuning/cli-reference.md` | `medium` | Launch RFT jobs using the eval-protocol CLI |
| [Remote Environment Setup](https://docs.fireworks.ai/fine-tuning/connect-environments.md) | `fine-tuning/connect-environments.md` | `medium` | Implement the /init endpoint to run evaluations in your infrastructure |
| [Debug SFT tokenization](https://docs.fireworks.ai/fine-tuning/debug-sft-tokenization.md) | `fine-tuning/debug-sft-tokenization.md` | `medium` | Download rendered token IDs and loss masks for supervised fine-tuning jobs. |
| [Deploying Fine Tuned Models](https://docs.fireworks.ai/fine-tuning/deploying-loras.md) | `fine-tuning/deploying-loras.md` | `medium` | Deploy one or multiple LoRA models fine tuned on Fireworks using live merge or multi-LoRA |
| [Agent Tracing](https://docs.fireworks.ai/fine-tuning/environments.md) | `fine-tuning/environments.md` | `medium` | Understand where your agent runs and how tracing enables reinforcement fine-tuning |
| [Evaluators](https://docs.fireworks.ai/fine-tuning/evaluators.md) | `fine-tuning/evaluators.md` | `medium` | Understand the fundamentals of evaluators and reward functions in reinforcement fine-tuning |
| [Supervised Fine Tuning - Vision](https://docs.fireworks.ai/fine-tuning/fine-tuning-vlm.md) | `fine-tuning/fine-tuning-vlm.md` | `medium` | Learn how to fine-tune vision-language models on Fireworks AI with image and text datasets |
| [Basics](https://docs.fireworks.ai/fine-tuning/how-rft-works.md) | `fine-tuning/how-rft-works.md` | `medium` | Understand the reinforcement learning fundamentals behind RFT |
| [Managed Fine-Tuning Overview](https://docs.fireworks.ai/fine-tuning/managed-finetuning-intro.md) | `fine-tuning/managed-finetuning-intro.md` | `medium` | Fine-tune models with Fireworks-managed infrastructure — no custom code required. |
| [Monitor Training](https://docs.fireworks.ai/fine-tuning/monitor-training.md) | `fine-tuning/monitor-training.md` | `medium` | Track RFT job progress and diagnose issues in real-time |
| [Price comparison vs Tinker](https://docs.fireworks.ai/fine-tuning/multi-turn-cost-comparison.md) | `fine-tuning/multi-turn-cost-comparison.md` | `medium` | Estimate the cost of multi-turn agentic RL rollouts on Fireworks compared to Tinker's per-token pricing |
| [Parameter Tuning](https://docs.fireworks.ai/fine-tuning/parameter-tuning.md) | `fine-tuning/parameter-tuning.md` | `medium` | Learn how training parameters affect model behavior and outcomes |
| [Single-Turn Training Quickstart](https://docs.fireworks.ai/fine-tuning/quickstart-math.md) | `fine-tuning/quickstart-math.md` | `medium` | Train a model to be an expert at answering GSM8K math questions |
| [Remote Agent Quickstart](https://docs.fireworks.ai/fine-tuning/quickstart-svg-agent.md) | `fine-tuning/quickstart-svg-agent.md` | `medium` | Train an SVG drawing agent running in a remote environment |
| [Overview](https://docs.fireworks.ai/fine-tuning/reinforcement-fine-tuning-models.md) | `fine-tuning/reinforcement-fine-tuning-models.md` | `medium` | Train models using reinforcement learning in minutes |
| [Cost Estimator](https://docs.fireworks.ai/fine-tuning/rft-cost-estimator.md) | `fine-tuning/rft-cost-estimator.md` | `medium` | Estimate and optimize the cost of your RFT training jobs |
| [RFT parameters reference](https://docs.fireworks.ai/fine-tuning/rft-parameters-reference.md) | `fine-tuning/rft-parameters-reference.md` | `medium` | Checkpoint, resume, and GRPO metrics fields for reinforcement fine-tuning recipes. |
| [Ledger & Debugging for RL Rollouts](https://docs.fireworks.ai/fine-tuning/rl-rollout-debugging.md) | `fine-tuning/rl-rollout-debugging.md` | `medium` | Inspect snapshot history, reset the ledger, and understand how in-flight requests behave during a weight swap. |
| [Incremental Snapshots (ARC2)](https://docs.fireworks.ai/fine-tuning/rl-rollout-delta-checkpoints.md) | `fine-tuning/rl-rollout-delta-checkpoints.md` | `medium` | Build ARC2 incremental checkpoints and signal delta hot-loads for BYOT RL rollout integrations. |
| [RL Rollouts with Your Own Trainer](https://docs.fireworks.ai/fine-tuning/rl-rollout-integration.md) | `fine-tuning/rl-rollout-integration.md` | `medium` | Integrate an external RL trainer with Fireworks inference: hot-load new checkpoints from your bucket and run rollouts via the OpenAI-compatible API. |
| [Secure Training (BYOB)](https://docs.fireworks.ai/fine-tuning/secure-fine-tuning.md) | `fine-tuning/secure-fine-tuning.md` | `medium` | Fine-tune models while keeping sensitive data and components under your control |
| [Checkpoints and Resume](https://docs.fireworks.ai/fine-tuning/training-api/cookbook/checkpoints.md) | `fine-tuning/training-api/cookbook/checkpoints.md` | `medium` | Save training progress, resume from failures, and promote checkpoints to deployable models — driven by the recipe. |
| [Cookbook: Distillation](https://docs.fireworks.ai/fine-tuning/training-api/cookbook/distillation.md) | `fine-tuning/training-api/cookbook/distillation.md` | `medium` | On-policy distillation recipes with one or more frozen teachers. |
| [Cookbook: DPO](https://docs.fireworks.ai/fine-tuning/training-api/cookbook/dpo.md) | `fine-tuning/training-api/cookbook/dpo.md` | `medium` | Direct Preference Optimization with pairwise data using the cookbook recipe. |
| [The Cookbook](https://docs.fireworks.ai/fine-tuning/training-api/cookbook/overview.md) | `fine-tuning/training-api/cookbook/overview.md` | `medium` | Ready-to-run training recipes for GRPO, DPO, SFT, and distillation built on top of the Training API. |
| [Cookbook Reference](https://docs.fireworks.ai/fine-tuning/training-api/cookbook/reference.md) | `fine-tuning/training-api/cookbook/reference.md` | `medium` | Configuration classes, checkpoint utilities, and advanced recipe knobs. |
| [Cookbook: Reinforcement Learning](https://docs.fireworks.ai/fine-tuning/training-api/cookbook/rl.md) | `fine-tuning/training-api/cookbook/rl.md` | `medium` | Async RL on Fireworks — write a rollout function, the recipe owns the loop (gate, advantage, weight sync, KL/TIS, PPO, checkpoints). Runs async or fully synchronous. |
| [Cookbook: SFT](https://docs.fireworks.ai/fine-tuning/training-api/cookbook/sft.md) | `fine-tuning/training-api/cookbook/sft.md` | `medium` | Supervised fine-tuning via the cookbook's sft_loop recipe. |
| [Weight sync](https://docs.fireworks.ai/fine-tuning/training-api/cookbook/weight-sync.md) | `fine-tuning/training-api/cookbook/weight-sync.md` | `medium` | How a trainer's updated weights reach the serving deployment during RL training. |
| [Introduction](https://docs.fireworks.ai/fine-tuning/training-api/introduction.md) | `fine-tuning/training-api/introduction.md` | `medium` | Fireworks Training API — custom training loops with full Python control over objectives, while Fireworks handles distributed GPU infrastructure. |
| [Loss Functions](https://docs.fireworks.ai/fine-tuning/training-api/loss-functions.md) | `fine-tuning/training-api/loss-functions.md` | `medium` | Built-in loss functions and custom objectives via forward_backward_custom. |
| [Quickstart](https://docs.fireworks.ai/fine-tuning/training-api/quickstart.md) | `fine-tuning/training-api/quickstart.md` | `medium` | Get a custom training loop running in minutes with the Fireworks Training API. |
| [Cleanup and Teardown](https://docs.fireworks.ai/fine-tuning/training-api/reference/cleanup.md) | `fine-tuning/training-api/reference/cleanup.md` | `medium` | Delete trainer jobs and deployments after experiments to avoid leaked resources. |
| [DeploymentManager (Compatibility)](https://docs.fireworks.ai/fine-tuning/training-api/reference/deployment-manager.md) | `fine-tuning/training-api/reference/deployment-manager.md` | `medium` | Legacy SDK reference for direct deployment lifecycle and weight-sync management. |
| [DeploymentSampler](https://docs.fireworks.ai/fine-tuning/training-api/reference/deployment-sampler.md) | `fine-tuning/training-api/reference/deployment-sampler.md` | `medium` | Client-side tokenized sampling from inference deployments for training and evaluation. |
| [FireworksClient](https://docs.fireworks.ai/fine-tuning/training-api/reference/fireworks-client.md) | `fine-tuning/training-api/reference/fireworks-client.md` | `medium` | Account-level operations that don't require a running trainer job. |
| [FiretitanServiceClient & TrainingClient](https://docs.fireworks.ai/fine-tuning/training-api/reference/service-client.md) | `fine-tuning/training-api/reference/service-client.md` | `medium` | Connect to a trainer endpoint and use the training client for forward/backward passes, optimizer steps, and checkpointing. |
| [TrainerJobManager (Compatibility)](https://docs.fireworks.ai/fine-tuning/training-api/reference/trainer-job-manager.md) | `fine-tuning/training-api/reference/trainer-job-manager.md` | `medium` | Legacy SDK reference for service-mode trainer job lifecycle management. |
| [WeightSyncer (Legacy)](https://docs.fireworks.ai/fine-tuning/training-api/reference/weight-syncer.md) | `fine-tuning/training-api/reference/weight-syncer.md` | `medium` | Backward-compatibility reference for the old standalone checkpoint-then-sync helper. |
| [Saving and Loading](https://docs.fireworks.ai/fine-tuning/training-api/saving-and-loading.md) | `fine-tuning/training-api/saving-and-loading.md` | `medium` | SDK-level reference for checkpoint save, load, weight sync, and promotion. |
| [Training and Sampling](https://docs.fireworks.ai/fine-tuning/training-api/training-and-sampling.md) | `fine-tuning/training-api/training-and-sampling.md` | `medium` | End-to-end SDK walkthrough: bootstrap resources, train, checkpoint, and sample through a serving deployment. |
| [Training Shapes](https://docs.fireworks.ai/fine-tuning/training-api/training-shapes.md) | `fine-tuning/training-api/training-shapes.md` | `medium` | Pre-configured GPU and model training profiles that simplify distributed training setup. |
| [Vision Inputs](https://docs.fireworks.ai/fine-tuning/training-api/vision-inputs.md) | `fine-tuning/training-api/vision-inputs.md` | `medium` | Fine-tune vision-language models (VLMs) with the Training API using multimodal chat data containing images and text. |
| [Training Prerequisites & Validation](https://docs.fireworks.ai/fine-tuning/training-prerequisites.md) | `fine-tuning/training-prerequisites.md` | `medium` | Requirements, validation checks, and common issues when launching RFT jobs |
| [Using Secrets](https://docs.fireworks.ai/fine-tuning/using-secret-in-evaluator.md) | `fine-tuning/using-secret-in-evaluator.md` | `medium` | Learn how to create secrets that can be utilized within your reward function. |
| [Warm Start from Fine-Tuned Models](https://docs.fireworks.ai/fine-tuning/warm-start.md) | `fine-tuning/warm-start.md` | `medium` | Continue training from a previously fine-tuned model with RFT |
| [Training Guide: UI](https://docs.fireworks.ai/fine-tuning/web-ui-guide.md) | `fine-tuning/web-ui-guide.md` | `medium` | Launch RFT jobs using the Fireworks dashboard |
| [Weighted Training](https://docs.fireworks.ai/fine-tuning/weighted-training.md) | `fine-tuning/weighted-training.md` | `medium` | Control which samples have greater influence during RFT training |

### Fireworks for Work

| Title | Path | Priority | Description |
|---|---|---|---|
| [Per-User Usage Limits](https://docs.fireworks.ai/fireworks-for-work/usage-limits.md) | `fireworks-for-work/usage-limits.md` | `low` | Set per-user spending limits on serverless inference — account defaults and per-user overrides |

### Getting started

| Title | Path | Priority | Description |
|---|---|---|---|
| [Concepts](https://docs.fireworks.ai/getting-started/concepts.md) | `getting-started/concepts.md` | `high` | This document outlines basic Fireworks AI concepts. |
| [Glossary](https://docs.fireworks.ai/getting-started/glossary.md) | `getting-started/glossary.md` | `high` | Definitions for key terms used across Fireworks AI documentation. |
| [Build with Fireworks AI](https://docs.fireworks.ai/getting-started/introduction.md) | `getting-started/introduction.md` | `high` | Fast inference and fine-tuning for open source models |
| [Deployments Quickstart](https://docs.fireworks.ai/getting-started/ondemand-quickstart.md) | `getting-started/ondemand-quickstart.md` | `high` | Deploy models on dedicated GPUs in minutes |
| [Serverless Quickstart](https://docs.fireworks.ai/getting-started/quickstart.md) | `getting-started/quickstart.md` | `high` | Make your first Serverless API call in minutes |

### Guides and optimization

| Title | Path | Priority | Description |
|---|---|---|---|
| [Batch API](https://docs.fireworks.ai/guides/batch-inference.md) | `guides/batch-inference.md` | `high` | Process large-scale async workloads at a discount |
| [Completions API](https://docs.fireworks.ai/guides/completions-api.md) | `guides/completions-api.md` | `high` | Use the completions API for raw text generation with custom prompt templates |
| [Tool Calling](https://docs.fireworks.ai/guides/function-calling.md) | `guides/function-calling.md` | `high` | Connect models to external tools and APIs |
| [Inference Error Codes](https://docs.fireworks.ai/guides/inference-error-codes.md) | `guides/inference-error-codes.md` | `high` | Common error codes, their meanings, and resolutions for inference requests |
| [Deployments](https://docs.fireworks.ai/guides/ondemand-deployments.md) | `guides/ondemand-deployments.md` | `high` | Configure and manage on-demand deployments on dedicated GPUs |
| [Using predicted outputs](https://docs.fireworks.ai/guides/predicted-outputs.md) | `guides/predicted-outputs.md` | `high` | Use Predicted Outputs to boost output generation speeds for editing / rewriting use cases |
| [Embeddings & Reranking](https://docs.fireworks.ai/guides/querying-embeddings-models.md) | `guides/querying-embeddings-models.md` | `high` | Generate embeddings and rerank results for semantic search |
| [Text Models](https://docs.fireworks.ai/guides/querying-text-models.md) | `guides/querying-text-models.md` | `high` | Query, track and manage inference for text models |
| [Vision Models](https://docs.fireworks.ai/guides/querying-vision-language-models.md) | `guides/querying-vision-language-models.md` | `high` | Query vision-language models to analyze images and visual content |
| [Account quotas](https://docs.fireworks.ai/guides/quotas_usage/account-quotas.md) | `guides/quotas_usage/account-quotas.md` | `high` | Account-wide request limits, spending tiers, budget controls, and on-demand GPU quotas |
| [Reasoning](https://docs.fireworks.ai/guides/reasoning.md) | `guides/reasoning.md` | `high` | How to use reasoning with Fireworks models |
| [Which model should I use?](https://docs.fireworks.ai/guides/recommended-models.md) | `guides/recommended-models.md` | `high` | Find the best open models for your use case or migrate from closed source models like Claude, GPT, and Gemini |
| [Reliability and Error Handling](https://docs.fireworks.ai/guides/reliability.md) | `guides/reliability.md` | `high` | Recommended patterns for timeouts, retries, and error handling when building production applications on the Fireworks API. |
| [Inference for RL Rollouts](https://docs.fireworks.ai/guides/rollout-inference.md) | `guides/rollout-inference.md` | `high` | Session affinity, KV-cache behavior, weight-swap behavior, and MoE Router Replay for rollout traffic on Fireworks inference deployments. |
| [Audit & Access Logs](https://docs.fireworks.ai/guides/security_compliance/audit_logs.md) | `guides/security_compliance/audit_logs.md` | `high` | Monitor and track account activities with audit logging for Enterprise accounts |
| [Zero Data Retention](https://docs.fireworks.ai/guides/security_compliance/data_handling.md) | `guides/security_compliance/data_handling.md` | `high` | Data retention policies at Fireworks |
| [Data Security](https://docs.fireworks.ai/guides/security_compliance/data_security.md) | `guides/security_compliance/data_security.md` | `high` | How we secure and handle your data for inference and training |
| [Understanding LoRA performance](https://docs.fireworks.ai/guides/understanding_lora_performance.md) | `guides/understanding_lora_performance.md` | `high` | Understand the performance impact of LoRA fine-tuning, optimization strategies, and deployment considerations. |
| [Video & Audio Inputs](https://docs.fireworks.ai/guides/video-audio-inputs.md) | `guides/video-audio-inputs.md` | `high` | Query multimodal models to process video and audio content directly |

### Model library and model-specific docs

| Title | Path | Priority | Description |
|---|---|---|---|
| [Kimi K2 family](https://docs.fireworks.ai/models/kimi-k2.md) | `models/kimi-k2.md` | `critical` | Using Kimi K2 family models in agentic and tool-calling workflows on Fireworks. |
| [Quantization](https://docs.fireworks.ai/models/quantization.md) | `models/quantization.md` | `critical` | Reduce model precision to improve performance and lower costs |
| [Upload via REST API](https://docs.fireworks.ai/models/uploading-custom-models-api.md) | `models/uploading-custom-models-api.md` | `critical` | Programmatically upload custom models using the Fireworks REST API |
| [Custom Models](https://docs.fireworks.ai/models/uploading-custom-models.md) | `models/uploading-custom-models.md` | `critical` | Upload, verify, and deploy your own models from Hugging Face or elsewhere |

### Serverless inference

| Title | Path | Priority | Description |
|---|---|---|---|
| [Serverless Overview](https://docs.fireworks.ai/serverless/overview.md) | `serverless/overview.md` | `critical` | How Serverless inference works on Fireworks: serving paths, billing, request/response headers, prompt caching, model lifecycle, and when to choose Serverless over On-demand |
| [Serverless Pricing](https://docs.fireworks.ai/serverless/pricing.md) | `serverless/pricing.md` | `critical` | Per-token serverless pricing for text, vision, and embedding models, including Priority and Fast serving paths |
| [Serverless Rate Limits](https://docs.fireworks.ai/serverless/rate-limits.md) | `serverless/rate-limits.md` | `critical` | Adaptive rate limits grow and shrink with your usage |
| [Serverless Serving Paths](https://docs.fireworks.ai/serverless/serving-paths.md) | `serverless/serving-paths.md` | `critical` | Standard, Priority, and Fast serving paths on Fireworks Serverless |

### Structured responses

| Title | Path | Priority | Description |
|---|---|---|---|
| [Structured Outputs](https://docs.fireworks.ai/structured-responses/structured-response-formatting.md) | `structured-responses/structured-response-formatting.md` | `low` | Enforce output formats using JSON schemas or custom grammars |

### Tools, SDKs and protocol compatibility

| Title | Path | Priority | Description |
|---|---|---|---|
| [Anthropic compatibility](https://docs.fireworks.ai/tools-sdks/anthropic-compatibility.md) | `tools-sdks/anthropic-compatibility.md` | `medium` | Use Anthropic SDKs with Fireworks, and understand the supported surface for the Anthropic-compatible Messages API. |
| [firectl account get](https://docs.fireworks.ai/tools-sdks/firectl/commands/account-get.md) | `tools-sdks/firectl/commands/account-get.md` | `medium` | Prints information about an account. |
| [firectl account list](https://docs.fireworks.ai/tools-sdks/firectl/commands/account-list.md) | `tools-sdks/firectl/commands/account-list.md` | `medium` | Prints all accounts the current signed-in user has access to. |
| [firectl api-key create](https://docs.fireworks.ai/tools-sdks/firectl/commands/api-key-create.md) | `tools-sdks/firectl/commands/api-key-create.md` | `medium` | Creates an API key for the signed in user or a specified service account user. |
| [firectl api-key delete](https://docs.fireworks.ai/tools-sdks/firectl/commands/api-key-delete.md) | `tools-sdks/firectl/commands/api-key-delete.md` | `medium` | Deletes an API key. |
| [firectl api-key get](https://docs.fireworks.ai/tools-sdks/firectl/commands/api-key-get.md) | `tools-sdks/firectl/commands/api-key-get.md` | `medium` | Prints information about an API key. |
| [firectl api-key list](https://docs.fireworks.ai/tools-sdks/firectl/commands/api-key-list.md) | `tools-sdks/firectl/commands/api-key-list.md` | `medium` | Prints all API keys for the signed in user. |
| [firectl audit-logs list](https://docs.fireworks.ai/tools-sdks/firectl/commands/audit-logs-list.md) | `tools-sdks/firectl/commands/audit-logs-list.md` | `medium` | Lists audit logs for the signed in user. |
| [Authentication](https://docs.fireworks.ai/tools-sdks/firectl/commands/authentication.md) | `tools-sdks/firectl/commands/authentication.md` | `medium` | Authentication for access to your account |
| [firectl batch-inference-job create](https://docs.fireworks.ai/tools-sdks/firectl/commands/batch-inference-job-create.md) | `tools-sdks/firectl/commands/batch-inference-job-create.md` | `medium` | Creates a batch inference job. |
| [firectl batch-inference-job delete](https://docs.fireworks.ai/tools-sdks/firectl/commands/batch-inference-job-delete.md) | `tools-sdks/firectl/commands/batch-inference-job-delete.md` | `medium` | Deletes a batch inference job. |
| [firectl batch-inference-job get](https://docs.fireworks.ai/tools-sdks/firectl/commands/batch-inference-job-get.md) | `tools-sdks/firectl/commands/batch-inference-job-get.md` | `medium` | Retrieves information about a batch inference job. |
| [firectl batch-inference-job list](https://docs.fireworks.ai/tools-sdks/firectl/commands/batch-inference-job-list.md) | `tools-sdks/firectl/commands/batch-inference-job-list.md` | `medium` | Lists all batch inference jobs in an account. |
| [firectl billing export-metrics](https://docs.fireworks.ai/tools-sdks/firectl/commands/billing-export-metrics.md) | `tools-sdks/firectl/commands/billing-export-metrics.md` | `medium` | Exports billing metrics |
| [firectl billing get-usage](https://docs.fireworks.ai/tools-sdks/firectl/commands/billing-get-usage.md) | `tools-sdks/firectl/commands/billing-get-usage.md` | `medium` | Prints account usage and rated costs for a time range. |
| [firectl billing list-invoices](https://docs.fireworks.ai/tools-sdks/firectl/commands/billing-list-invoices.md) | `tools-sdks/firectl/commands/billing-list-invoices.md` | `medium` | Prints information about invoices. |
| [firectl billing notification-settings get](https://docs.fireworks.ai/tools-sdks/firectl/commands/billing-notification-settings-get.md) | `tools-sdks/firectl/commands/billing-notification-settings-get.md` | `medium` | Get notification settings for an account. |
| [firectl billing notification-settings update](https://docs.fireworks.ai/tools-sdks/firectl/commands/billing-notification-settings-update.md) | `tools-sdks/firectl/commands/billing-notification-settings-update.md` | `medium` | Update notification settings for an account. |
| [firectl billing notification-settings](https://docs.fireworks.ai/tools-sdks/firectl/commands/billing-notification-settings.md) | `tools-sdks/firectl/commands/billing-notification-settings.md` | `medium` | Manage notification settings. |
| [firectl credit-redemption list](https://docs.fireworks.ai/tools-sdks/firectl/commands/credit-redemption-list.md) | `tools-sdks/firectl/commands/credit-redemption-list.md` | `medium` | Lists credit code redemptions for the current account. |
| [firectl credit-redemption redeem](https://docs.fireworks.ai/tools-sdks/firectl/commands/credit-redemption-redeem.md) | `tools-sdks/firectl/commands/credit-redemption-redeem.md` | `medium` | Redeems a credit code. |
| [firectl dataset create](https://docs.fireworks.ai/tools-sdks/firectl/commands/dataset-create.md) | `tools-sdks/firectl/commands/dataset-create.md` | `medium` | Creates and uploads a dataset. |
| [firectl dataset delete](https://docs.fireworks.ai/tools-sdks/firectl/commands/dataset-delete.md) | `tools-sdks/firectl/commands/dataset-delete.md` | `medium` | Deletes a dataset. |
| [firectl dataset download](https://docs.fireworks.ai/tools-sdks/firectl/commands/dataset-download.md) | `tools-sdks/firectl/commands/dataset-download.md` | `medium` | Downloads a dataset to a local directory. |
| [firectl dataset get](https://docs.fireworks.ai/tools-sdks/firectl/commands/dataset-get.md) | `tools-sdks/firectl/commands/dataset-get.md` | `medium` | Prints information about a dataset. |
| [firectl dataset list](https://docs.fireworks.ai/tools-sdks/firectl/commands/dataset-list.md) | `tools-sdks/firectl/commands/dataset-list.md` | `medium` | Prints all datasets in an account. |
| [firectl dataset update](https://docs.fireworks.ai/tools-sdks/firectl/commands/dataset-update.md) | `tools-sdks/firectl/commands/dataset-update.md` | `medium` | Updates a dataset. |
| [firectl deployed-model get](https://docs.fireworks.ai/tools-sdks/firectl/commands/deployed-model-get.md) | `tools-sdks/firectl/commands/deployed-model-get.md` | `medium` | Prints information about a deployed model. |
| [firectl deployed-model list](https://docs.fireworks.ai/tools-sdks/firectl/commands/deployed-model-list.md) | `tools-sdks/firectl/commands/deployed-model-list.md` | `medium` | Prints all deployed models in the account. |
| [firectl deployed-model update](https://docs.fireworks.ai/tools-sdks/firectl/commands/deployed-model-update.md) | `tools-sdks/firectl/commands/deployed-model-update.md` | `medium` | Update a deployed model. |
| [firectl deployment create](https://docs.fireworks.ai/tools-sdks/firectl/commands/deployment-create.md) | `tools-sdks/firectl/commands/deployment-create.md` | `medium` | Creates a new deployment. |
| [firectl deployment delete](https://docs.fireworks.ai/tools-sdks/firectl/commands/deployment-delete.md) | `tools-sdks/firectl/commands/deployment-delete.md` | `medium` | Deletes a deployment. |
| [firectl deployment get](https://docs.fireworks.ai/tools-sdks/firectl/commands/deployment-get.md) | `tools-sdks/firectl/commands/deployment-get.md` | `medium` | Prints information about a deployment. |
| [firectl deployment list](https://docs.fireworks.ai/tools-sdks/firectl/commands/deployment-list.md) | `tools-sdks/firectl/commands/deployment-list.md` | `medium` | Prints all deployments in the account. |
| [firectl deployment scale](https://docs.fireworks.ai/tools-sdks/firectl/commands/deployment-scale.md) | `tools-sdks/firectl/commands/deployment-scale.md` | `medium` | Scales a deployment to a specified number of replicas. |
| [firectl deployment-shape-version get](https://docs.fireworks.ai/tools-sdks/firectl/commands/deployment-shape-version-get.md) | `tools-sdks/firectl/commands/deployment-shape-version-get.md` | `medium` | Prints information about a deployment shape version. |
| [firectl deployment-shape-version list](https://docs.fireworks.ai/tools-sdks/firectl/commands/deployment-shape-version-list.md) | `tools-sdks/firectl/commands/deployment-shape-version-list.md` | `medium` | Prints all deployment shape versions of this deployment shape. |
| [firectl deployment undelete](https://docs.fireworks.ai/tools-sdks/firectl/commands/deployment-undelete.md) | `tools-sdks/firectl/commands/deployment-undelete.md` | `medium` | Undeletes a deployment. |
| [firectl deployment update](https://docs.fireworks.ai/tools-sdks/firectl/commands/deployment-update.md) | `tools-sdks/firectl/commands/deployment-update.md` | `medium` | Update a deployment. |
| [firectl dpo-job cancel](https://docs.fireworks.ai/tools-sdks/firectl/commands/dpo-job-cancel.md) | `tools-sdks/firectl/commands/dpo-job-cancel.md` | `medium` | Cancels a running dpo job. |
| [firectl dpo-job create](https://docs.fireworks.ai/tools-sdks/firectl/commands/dpo-job-create.md) | `tools-sdks/firectl/commands/dpo-job-create.md` | `medium` | Creates a dpo job. |
| [firectl dpo-job delete](https://docs.fireworks.ai/tools-sdks/firectl/commands/dpo-job-delete.md) | `tools-sdks/firectl/commands/dpo-job-delete.md` | `medium` | Deletes a dpo job. |
| [firectl dpo-job export-metrics](https://docs.fireworks.ai/tools-sdks/firectl/commands/dpo-job-export-metrics.md) | `tools-sdks/firectl/commands/dpo-job-export-metrics.md` | `medium` | Exports metrics for a dpo job. |
| [firectl dpo-job get](https://docs.fireworks.ai/tools-sdks/firectl/commands/dpo-job-get.md) | `tools-sdks/firectl/commands/dpo-job-get.md` | `medium` | Retrieves information about a dpo job. |
| [firectl dpo-job list](https://docs.fireworks.ai/tools-sdks/firectl/commands/dpo-job-list.md) | `tools-sdks/firectl/commands/dpo-job-list.md` | `medium` | Lists all dpo jobs in an account. |
| [firectl dpo-job resume](https://docs.fireworks.ai/tools-sdks/firectl/commands/dpo-job-resume.md) | `tools-sdks/firectl/commands/dpo-job-resume.md` | `medium` | Resumes a dpo job. |
| [firectl evaluator-revision alias](https://docs.fireworks.ai/tools-sdks/firectl/commands/evaluator-revision-alias.md) | `tools-sdks/firectl/commands/evaluator-revision-alias.md` | `medium` | Alias an evaluator revision |
| [firectl evaluator-revision delete](https://docs.fireworks.ai/tools-sdks/firectl/commands/evaluator-revision-delete.md) | `tools-sdks/firectl/commands/evaluator-revision-delete.md` | `medium` | Delete an evaluator revision |
| [firectl evaluator-revision get](https://docs.fireworks.ai/tools-sdks/firectl/commands/evaluator-revision-get.md) | `tools-sdks/firectl/commands/evaluator-revision-get.md` | `medium` | Get an evaluator revision |
| [firectl evaluator-revision list](https://docs.fireworks.ai/tools-sdks/firectl/commands/evaluator-revision-list.md) | `tools-sdks/firectl/commands/evaluator-revision-list.md` | `medium` | List evaluator revisions |
| [firectl identity-provider create](https://docs.fireworks.ai/tools-sdks/firectl/commands/identity-provider-create.md) | `tools-sdks/firectl/commands/identity-provider-create.md` | `medium` | Creates a new identity provider. |
| [firectl identity-provider get](https://docs.fireworks.ai/tools-sdks/firectl/commands/identity-provider-get.md) | `tools-sdks/firectl/commands/identity-provider-get.md` | `medium` | Prints information about an identity provider. |
| [firectl identity-provider list](https://docs.fireworks.ai/tools-sdks/firectl/commands/identity-provider-list.md) | `tools-sdks/firectl/commands/identity-provider-list.md` | `medium` | List identity providers for an account |
| [firectl model create](https://docs.fireworks.ai/tools-sdks/firectl/commands/model-create.md) | `tools-sdks/firectl/commands/model-create.md` | `medium` | Creates and uploads a model. |
| [firectl model delete](https://docs.fireworks.ai/tools-sdks/firectl/commands/model-delete.md) | `tools-sdks/firectl/commands/model-delete.md` | `medium` | Deletes a model. |
| [firectl model download](https://docs.fireworks.ai/tools-sdks/firectl/commands/model-download.md) | `tools-sdks/firectl/commands/model-download.md` | `medium` | Download a model. |
| [firectl model get](https://docs.fireworks.ai/tools-sdks/firectl/commands/model-get.md) | `tools-sdks/firectl/commands/model-get.md` | `medium` | Prints information about a model. |
| [firectl model list](https://docs.fireworks.ai/tools-sdks/firectl/commands/model-list.md) | `tools-sdks/firectl/commands/model-list.md` | `medium` | Prints all models in an account. |
| [firectl model load-lora](https://docs.fireworks.ai/tools-sdks/firectl/commands/model-load-lora.md) | `tools-sdks/firectl/commands/model-load-lora.md` | `medium` | Loads a LoRA model. |
| [firectl model prepare](https://docs.fireworks.ai/tools-sdks/firectl/commands/model-prepare.md) | `tools-sdks/firectl/commands/model-prepare.md` | `medium` | Prepare models for different precisions |
| [firectl model unload-lora](https://docs.fireworks.ai/tools-sdks/firectl/commands/model-unload-lora.md) | `tools-sdks/firectl/commands/model-unload-lora.md` | `medium` | Unloads a LoRA model. |
| [firectl model update](https://docs.fireworks.ai/tools-sdks/firectl/commands/model-update.md) | `tools-sdks/firectl/commands/model-update.md` | `medium` | Updates a model. |
| [firectl model upload](https://docs.fireworks.ai/tools-sdks/firectl/commands/model-upload.md) | `tools-sdks/firectl/commands/model-upload.md` | `medium` | Resumes or completes a model upload. |
| [firectl quota get](https://docs.fireworks.ai/tools-sdks/firectl/commands/quota-get.md) | `tools-sdks/firectl/commands/quota-get.md` | `medium` | Prints information about a quota. |
| [firectl quota list](https://docs.fireworks.ai/tools-sdks/firectl/commands/quota-list.md) | `tools-sdks/firectl/commands/quota-list.md` | `medium` | Prints all quotas. |
| [firectl quota update](https://docs.fireworks.ai/tools-sdks/firectl/commands/quota-update.md) | `tools-sdks/firectl/commands/quota-update.md` | `medium` | Updates a quota. |
| [firectl reinforcement-fine-tuning-job cancel](https://docs.fireworks.ai/tools-sdks/firectl/commands/reinforcement-fine-tuning-job-cancel.md) | `tools-sdks/firectl/commands/reinforcement-fine-tuning-job-cancel.md` | `medium` | Cancels a running reinforcement fine-tuning job. |
| [firectl reinforcement-fine-tuning-job create](https://docs.fireworks.ai/tools-sdks/firectl/commands/reinforcement-fine-tuning-job-create.md) | `tools-sdks/firectl/commands/reinforcement-fine-tuning-job-create.md` | `medium` | Creates a reinforcement fine-tuning job. |
| [firectl reinforcement-fine-tuning-job delete](https://docs.fireworks.ai/tools-sdks/firectl/commands/reinforcement-fine-tuning-job-delete.md) | `tools-sdks/firectl/commands/reinforcement-fine-tuning-job-delete.md` | `medium` | Deletes a reinforcement fine-tuning job. |
| [firectl reinforcement-fine-tuning-job get](https://docs.fireworks.ai/tools-sdks/firectl/commands/reinforcement-fine-tuning-job-get.md) | `tools-sdks/firectl/commands/reinforcement-fine-tuning-job-get.md` | `medium` | Retrieves information about a reinforcement fine-tuning job. |
| [firectl reinforcement-fine-tuning-job list](https://docs.fireworks.ai/tools-sdks/firectl/commands/reinforcement-fine-tuning-job-list.md) | `tools-sdks/firectl/commands/reinforcement-fine-tuning-job-list.md` | `medium` | Lists all reinforcement fine-tuning jobs in an account. |
| [firectl reinforcement-fine-tuning-job resume](https://docs.fireworks.ai/tools-sdks/firectl/commands/reinforcement-fine-tuning-job-resume.md) | `tools-sdks/firectl/commands/reinforcement-fine-tuning-job-resume.md` | `medium` | Resumes a failed reinforcement fine-tuning job. |
| [firectl reinforcement-fine-tuning-job update](https://docs.fireworks.ai/tools-sdks/firectl/commands/reinforcement-fine-tuning-job-update.md) | `tools-sdks/firectl/commands/reinforcement-fine-tuning-job-update.md` | `medium` | Update fields on a reinforcement fine-tuning job. |
| [firectl reservation get](https://docs.fireworks.ai/tools-sdks/firectl/commands/reservation-get.md) | `tools-sdks/firectl/commands/reservation-get.md` | `medium` | Prints information about a reservation. |
| [firectl reservation list](https://docs.fireworks.ai/tools-sdks/firectl/commands/reservation-list.md) | `tools-sdks/firectl/commands/reservation-list.md` | `medium` | Prints active reservations. |
| [firectl rlor-trainer-job cancel](https://docs.fireworks.ai/tools-sdks/firectl/commands/rlor-trainer-job-cancel.md) | `tools-sdks/firectl/commands/rlor-trainer-job-cancel.md` | `medium` | Cancels a running rlor trainer job. |
| [firectl rlor-trainer-job create](https://docs.fireworks.ai/tools-sdks/firectl/commands/rlor-trainer-job-create.md) | `tools-sdks/firectl/commands/rlor-trainer-job-create.md` | `medium` | Creates a rlor trainer job. |
| [firectl rlor-trainer-job delete](https://docs.fireworks.ai/tools-sdks/firectl/commands/rlor-trainer-job-delete.md) | `tools-sdks/firectl/commands/rlor-trainer-job-delete.md` | `medium` | Deletes a rlor trainer job. |
| [firectl rlor-trainer-job get](https://docs.fireworks.ai/tools-sdks/firectl/commands/rlor-trainer-job-get.md) | `tools-sdks/firectl/commands/rlor-trainer-job-get.md` | `medium` | Retrieves information about a rlor trainer job. |
| [firectl rlor-trainer-job list](https://docs.fireworks.ai/tools-sdks/firectl/commands/rlor-trainer-job-list.md) | `tools-sdks/firectl/commands/rlor-trainer-job-list.md` | `medium` | Lists all rlor trainer jobs in an account. |
| [firectl router create](https://docs.fireworks.ai/tools-sdks/firectl/commands/router-create.md) | `tools-sdks/firectl/commands/router-create.md` | `medium` | Creates a router. |
| [firectl router delete](https://docs.fireworks.ai/tools-sdks/firectl/commands/router-delete.md) | `tools-sdks/firectl/commands/router-delete.md` | `medium` | Deletes a router. |
| [firectl router get](https://docs.fireworks.ai/tools-sdks/firectl/commands/router-get.md) | `tools-sdks/firectl/commands/router-get.md` | `medium` | Prints information about a router. |
| [firectl router list](https://docs.fireworks.ai/tools-sdks/firectl/commands/router-list.md) | `tools-sdks/firectl/commands/router-list.md` | `medium` | Prints all routers in the account. |
| [firectl router update](https://docs.fireworks.ai/tools-sdks/firectl/commands/router-update.md) | `tools-sdks/firectl/commands/router-update.md` | `medium` | Update a router. |
| [firectl secret create](https://docs.fireworks.ai/tools-sdks/firectl/commands/secret-create.md) | `tools-sdks/firectl/commands/secret-create.md` | `medium` | Creates a secret for the signed in user. |
| [firectl secret delete](https://docs.fireworks.ai/tools-sdks/firectl/commands/secret-delete.md) | `tools-sdks/firectl/commands/secret-delete.md` | `medium` | Deletes a secret. |
| [firectl secret get](https://docs.fireworks.ai/tools-sdks/firectl/commands/secret-get.md) | `tools-sdks/firectl/commands/secret-get.md` | `medium` | Retrieves a secret by name. |
| [firectl secret list](https://docs.fireworks.ai/tools-sdks/firectl/commands/secret-list.md) | `tools-sdks/firectl/commands/secret-list.md` | `medium` | Lists all secrets for the signed in user. |
| [firectl secret update](https://docs.fireworks.ai/tools-sdks/firectl/commands/secret-update.md) | `tools-sdks/firectl/commands/secret-update.md` | `medium` | Updates an existing secret. |
| [firectl set-api-key](https://docs.fireworks.ai/tools-sdks/firectl/commands/set-api-key.md) | `tools-sdks/firectl/commands/set-api-key.md` | `medium` | Sets the default API key in ~/.fireworks/auth.ini. |
| [firectl supervised-fine-tuning-job cancel](https://docs.fireworks.ai/tools-sdks/firectl/commands/supervised-fine-tuning-job-cancel.md) | `tools-sdks/firectl/commands/supervised-fine-tuning-job-cancel.md` | `medium` | Cancels a running supervised fine-tuning job. |
| [firectl supervised-fine-tuning-job create](https://docs.fireworks.ai/tools-sdks/firectl/commands/supervised-fine-tuning-job-create.md) | `tools-sdks/firectl/commands/supervised-fine-tuning-job-create.md` | `medium` | Creates a supervised fine-tuning job. |
| [firectl supervised-fine-tuning-job delete](https://docs.fireworks.ai/tools-sdks/firectl/commands/supervised-fine-tuning-job-delete.md) | `tools-sdks/firectl/commands/supervised-fine-tuning-job-delete.md` | `medium` | Deletes a supervised fine-tuning job. |
| [firectl supervised-fine-tuning-job get](https://docs.fireworks.ai/tools-sdks/firectl/commands/supervised-fine-tuning-job-get.md) | `tools-sdks/firectl/commands/supervised-fine-tuning-job-get.md` | `medium` | Retrieves information about a supervised fine-tuning job. |
| [firectl supervised-fine-tuning-job list](https://docs.fireworks.ai/tools-sdks/firectl/commands/supervised-fine-tuning-job-list.md) | `tools-sdks/firectl/commands/supervised-fine-tuning-job-list.md` | `medium` | Lists all supervised fine-tuning jobs in an account. |
| [firectl training-shape clone](https://docs.fireworks.ai/tools-sdks/firectl/commands/training-shape-clone.md) | `tools-sdks/firectl/commands/training-shape-clone.md` | `medium` | Clones an existing training shape to a new shape. |
| [firectl training-shape create](https://docs.fireworks.ai/tools-sdks/firectl/commands/training-shape-create.md) | `tools-sdks/firectl/commands/training-shape-create.md` | `medium` | Creates a new training shape. |
| [firectl training-shape delete](https://docs.fireworks.ai/tools-sdks/firectl/commands/training-shape-delete.md) | `tools-sdks/firectl/commands/training-shape-delete.md` | `medium` | Deletes a training shape and all its versions. |
| [firectl training-shape get](https://docs.fireworks.ai/tools-sdks/firectl/commands/training-shape-get.md) | `tools-sdks/firectl/commands/training-shape-get.md` | `medium` | Prints information about a training shape. |
| [firectl training-shape list](https://docs.fireworks.ai/tools-sdks/firectl/commands/training-shape-list.md) | `tools-sdks/firectl/commands/training-shape-list.md` | `medium` | Lists training shapes in the account. |
| [firectl training-shape update](https://docs.fireworks.ai/tools-sdks/firectl/commands/training-shape-update.md) | `tools-sdks/firectl/commands/training-shape-update.md` | `medium` | Updates a training shape (mutable fields only). Creates a new version automatically. |
| [firectl training-shape-version get](https://docs.fireworks.ai/tools-sdks/firectl/commands/training-shape-version-get.md) | `tools-sdks/firectl/commands/training-shape-version-get.md` | `medium` | Prints information about a training shape version. |
| [firectl training-shape-version list](https://docs.fireworks.ai/tools-sdks/firectl/commands/training-shape-version-list.md) | `tools-sdks/firectl/commands/training-shape-version-list.md` | `medium` | Lists training shape versions. |
| [firectl training-shape-version update](https://docs.fireworks.ai/tools-sdks/firectl/commands/training-shape-version-update.md) | `tools-sdks/firectl/commands/training-shape-version-update.md` | `medium` | Update a training shape version. |
| [firectl upgrade](https://docs.fireworks.ai/tools-sdks/firectl/commands/upgrade.md) | `tools-sdks/firectl/commands/upgrade.md` | `medium` | Upgrades the firectl binary to the latest version. |
| [firectl user create](https://docs.fireworks.ai/tools-sdks/firectl/commands/user-create.md) | `tools-sdks/firectl/commands/user-create.md` | `medium` | Creates a new user. |
| [firectl user delete](https://docs.fireworks.ai/tools-sdks/firectl/commands/user-delete.md) | `tools-sdks/firectl/commands/user-delete.md` | `medium` | Deletes a user. |
| [firectl user get](https://docs.fireworks.ai/tools-sdks/firectl/commands/user-get.md) | `tools-sdks/firectl/commands/user-get.md` | `medium` | Prints information about a user. |
| [firectl user list](https://docs.fireworks.ai/tools-sdks/firectl/commands/user-list.md) | `tools-sdks/firectl/commands/user-list.md` | `medium` | Prints all users in the account. |
| [firectl user update](https://docs.fireworks.ai/tools-sdks/firectl/commands/user-update.md) | `tools-sdks/firectl/commands/user-update.md` | `medium` | Updates a user. |
| [firectl version](https://docs.fireworks.ai/tools-sdks/firectl/commands/version.md) | `tools-sdks/firectl/commands/version.md` | `medium` | Prints the version of firectl |
| [firectl whoami](https://docs.fireworks.ai/tools-sdks/firectl/commands/whoami.md) | `tools-sdks/firectl/commands/whoami.md` | `medium` | Shows the currently authenticated user |
| [Getting started](https://docs.fireworks.ai/tools-sdks/firectl/firectl.md) | `tools-sdks/firectl/firectl.md` | `medium` | Learn to create, deploy, and manage resources using Firectl |
