# Fireworks LoRA & Fine-Tuning Strategy

Updated on: 2026-07-09

## Strategic Decision

LoRA should not enter the main submission path of Track 1 without explicit confirmation from the evaluator.

Reason: Track 1 restricts the selection to `ALLOWED_MODELS`, while the Fireworks documentation states that fine-tuned LoRA models can only be deployed in on-demand dedicated deployments, not in Serverless. A LoRA in live merge or multi-LoRA changes the `model` to a fine-tuned/deployment ID, potentially outside the allowed list and outside the comparability of the scoring.

Therefore:

- main path: local solvers + matrix/Nash + allowed Fireworks models;
- router fine-tuning: allowed and compatible with scoring, as long as the final output continues to respect accuracy and Fireworks token count;
- LoRA path as a response model: optional research/calibration, behind a feature flag, never default;
- competitive use: only if the official guide or harness exposes a LoRA/fine-tuned model in `ALLOWED_MODELS`.

## Important Distinction

The official text allows fine-tuning the router. This is different from replacing the response model with a Fireworks LoRA outside the allowed set.

Safe and aligned:

- train a local regression/matrix to choose the smallest sufficient model;
- fine-tune a local classifier that decides `local_solver`, `cheap_fireworks`, `strong_fireworks`, or `abstain`;
- calibrate risk thresholds with microbench data;
- use the fine-tuned router to reduce Fireworks calls without changing the final allowed models.

Conditioned on the harness:

- call a fine-tuned Fireworks model as a final response;
- use multi-LoRA with `model="<fine_tuned_model>#<deployment>"`;
- replace `minimax-m3`, `kimi-k2p7-code`, or allowed Gemma with an own deployment.

Rule of thumb: fine-tuning the routing decision is good; fine-tuning the responding model is only included if the evaluator accepts that endpoint/model ID.

## What the Official Documentation Says

Sources:

- Fireworks Managed Fine-Tuning Overview: https://docs.fireworks.ai/fine-tuning/managed-finetuning-intro
- Fireworks Deploying Fine Tuned Models: https://docs.fireworks.ai/fine-tuning/deploying-loras
- Fireworks Understanding LoRA Performance: https://docs.fireworks.ai/guides/understanding_lora_performance
- Fireworks Model Library: https://app.fireworks.ai/models

Relevant points:

- Managed fine-tuning supports major open families, including Gemma, Kimi, DeepSeek, Qwen, GLM, and Llama, when the base model has a compatible training shape.
- Gemma `gemma-4-26b-a4b-it` and `gemma-4-31b-it` appear in the fine-tuning table with a maximum context of `256K`.
- LoRA is recommended when we want efficient adapter training and flexibility to serve multiple adapters.
- Full-parameter tuning is suitable when the task requires altering all weights for reasoning, alignment, or difficult domain adaptation.
- Fine-tuned LoRA models can only be deployed in on-demand dedicated deployments; Fireworks states that Serverless does not support LoRA.
- Fireworks offers two LoRA deployment modes: live merge and multi-LoRA.
- Live merge fuses the LoRA weights at deployment, removing inference overhead and matching the behavior of a native fine-tune.
- Multi-LoRA allows multiple adapters on a single deployment, but adds per-request overhead.
- For multi-LoRA, the request must use `model="<fine_tuned_model>#<deployment>"`; the old `deployedModel` key is deprecated.
- FP8/FP4 quantized shapes do not support `--enable-addons`; LoRA addon requires BF16 or merge.
- Unmerged LoRA can increase TTFT by around `10-30%` and reduce throughput under concurrency.

## Fit with Track 1

Track 1 rewards a lower token count after the accuracy gate. Fine-tuning the router can reduce tokens if it avoids calls or safely chooses smaller models. Fine-tuning the responding model can improve the accuracy of a small model, but does not automatically reduce tokens:

- Fireworks tokens still count if inference goes through `FIREWORKS_BASE_URL`;
- if the LoRA requires its own deployment, it may fall outside the official set of allowed models;
- if the local response already covers mechanical subcases with zero tokens, LoRA competes against a better option: not calling Fireworks;
- if the problem is routing, a fine-tuned model still needs to receive a prompt and produce a response, so it may use more tokens than a local rule/solver.

Conclusion: LoRA would only make sense for the residual range of tasks that:

- are not mechanically solvable;
- appear with a repeated pattern in the evaluator;
- currently require an expensive model to pass accuracy;
- can be answered by a smaller/fine-tuned model with fewer tokens;
- and are accepted by the harness as an allowed model.

## Safe Uses Now

Without depending on official acceptance:

- study the Model Library to see which allowed models are tunable/deployable;
- prepare a routing/format-following SFT dataset from local microbenches;
- use LoRA only as a lab sandbox to measure if Gemma/Minimax/Kimi improves in strict formatting;
- do not publish a final image pointing to LoRA;
- do not change `ALLOWED_MODELS` to a fine-tuned ID in the submission path.

## Proposed Feature Flag

If the regulations release fine-tuned deployments, implement behind these variables:

```bash
ENABLE_FIREWORKS_LORA=0
FIREWORKS_LORA_MODEL=
FIREWORKS_LORA_DEPLOYMENT=
FIREWORKS_LORA_MODE=disabled  # disabled|live_merge|multi_lora
```

Rules:

- default always `disabled`;
- fail closed if `FIREWORKS_LORA_MODEL` is not in `ALLOWED_MODELS` or if `ALLOW_UNLISTED_LORA=1` is not explicitly defined for lab testing;
- record in metadata when LoRA is used;
- separate LoRA cost/latency/validacy in reports so as not to contaminate the official matrix.

## Minimal Experiment if Released

1. Create an SFT dataset with inputs of type `prompt -> answer` only for strict format and categories where Fireworks fails due to wrappers/extraneous prose.
2. Train a short LoRA on an allowed base, preferably Gemma if the Gemma bonus remains relevant.
3. Deploy live merge, not multi-LoRA, if there is only one adapter; this avoids overhead.
4. Run `scripts/fireworks_microbench.py` on the same dataset as the allowed models.
5. Accept LoRA only if it passes these gates:

- mechanical validity greater than or equal to the best allowed model;
- total tokens fewer than the best allowed model in the same category;
- latency within the official budget;
- ID accepted by the harness or explicitly listed in `ALLOWED_MODELS`;
- submission audit documents the regulatory risk.

## Current Decision

Do not implement LoRA in the main runtime for now.

Best immediate competitive return:

- expand zero-token adversarial gates;
- keep Gemma in the project via allowed models/local AMD when accessible;
- use Fireworks allowed models as a fallback controlled by matrix/regression/Nash;
- spend credit only on microbenches that improve routing weights or reveal solver/format failures..
