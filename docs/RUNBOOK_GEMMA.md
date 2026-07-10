# Gemma Runbook

## Roles

The project uses two small local Gemma models with separate responsibilities:

| Model | Role | Final precision |
|---|---|---|
| FunctionGemma 270M IT | Intent plus five-score assessment | Start with 8-bit |
| Gemma 4 E2B IT | Local text-only answer generation | Official mobile/QAT artifact |

Large Gemma 26B/31B models are development, teacher or allowed Fireworks routes. They are not bundled in the final 4 GB container.

## AMD Pod

Use the organizer-provided ROCm/PyTorch environment and validate it with:

```bash
/opt/venv/bin/python scripts/amd_pod_doctor.py --json
```

Do not replace the pod's ROCm-enabled PyTorch. Train FunctionGemma with [`FUNCTIONGEMMA_270M_AMD_TRAINING_TUTORIAL.md`](./FUNCTIONGEMMA_270M_AMD_TRAINING_TUTORIAL.md).

## FunctionGemma Runtime

- one `assess_task` tool call only;
- no free-form answer;
- strict intent, sub-intent and score schema;
- low decode budget;
- no engine or model selection in model output;
- parse failure enters Fireworks-safe mode;
- exact router specification in [`FUNCTIONGEMMA_ROUTER_SPEC.md`](./FUNCTIONGEMMA_ROUTER_SPEC.md).

## E2B Runtime

Use `litert-community/gemma-4-E2B-it-litert-lm` through LiteRT-LM on Linux `x86_64`. Keep vision and audio unloaded, cap context and output, and test beside FunctionGemma under the final resource constraints.

Detailed runtime gates: [`GEMMA_E2B_TEXT_ONLY_RUNTIME.md`](./GEMMA_E2B_TEXT_ONLY_RUNTIME.md).

## Promotion

Fireworks-only remains the champion until the combined local image matches accuracy, lowers Fireworks tokens, fits 4 GB RAM and completes the official batch within 10 minutes.
