# Track 1 Final Environment Strategy

Updated: 2026-07-09

## What The Latest Guide Establishes

Track 1 is a general-purpose AI agent benchmark across eight categories:

- factual knowledge;
- mathematical reasoning;
- sentiment classification;
- text summarisation;
- named entity recognition;
- code debugging;
- logical / deductive reasoning;
- code generation.

The submitted Docker image must:

- read `/input/tasks.json`;
- write `/output/results.json`;
- exit `0` on success;
- use only environment-injected `FIREWORKS_API_KEY`, `FIREWORKS_BASE_URL` and `ALLOWED_MODELS`;
- route every Fireworks call through `FIREWORKS_BASE_URL`;
- use only models listed in `ALLOWED_MODELS`;
- finish within 10 minutes;
- stay below the `10 GB` compressed image cap;
- include a `linux/amd64` manifest.

The final grading environment is constrained:

- `4 GB` RAM;
- `2 vCPU`;
- no promised GPU endpoint;
- local models are allowed, but must fit the envelope;
- the guide calls `2B-3B` 4-bit quantized models safe;
- the guide warns that `7B` 4-bit can consume the full RAM budget.

`ZERO_API_CALLS` is not a failure marker. It only means no calls went through the Fireworks proxy. Local answers still count for accuracy, but they only help if the local model or local logic is correct.

## Critical Correction

The Docker image is not the AMD GPU pod.

The AMD notebook/pod is a development and calibration environment. It can run heavier Gemma experiments, vLLM/SGLang tests, prompt studies and fine-tuning experiments.

The final scoring container must survive the official `4 GB` RAM / `2 vCPU` environment unless the organizers explicitly provide another endpoint. Therefore, Gemma 26B/31B should not be treated as a local final-container model.

## Small Gemma Correction

The final-container restriction does not eliminate local Gemma. It eliminates large local Gemma.

The attached Gemma material introduces smaller Gemma 4 variants such as E2B and E4B, and the Track 1 guide explicitly allows local models sized for the `4 GB` RAM / `2 vCPU` environment. Therefore, a Gemma E2B-class 4-bit local model is a legitimate challenger path.

The correct posture:

- evaluate small Gemma locally as a verifier, triage classifier or short-answer draft model;
- keep Fireworks as the safe default until the small model passes memory, latency and accuracy gates;
- do not promote E4B, 12B, 26B or 31B to final local runtime without proof under the official envelope;
- prefer short context and short output budgets for local inference.

Detailed strategy: [`docs/GEMMA_SMALL_LOCAL_STRATEGY.md`](./GEMMA_SMALL_LOCAL_STRATEGY.md).

## Where Gemma Still Fits

Gemma remains strategically important, but there are four separate lanes:

1. Fireworks allowed lane: use Gemma directly if a Gemma model or deployment ID appears in `ALLOWED_MODELS` and works through `FIREWORKS_BASE_URL`.
2. AMD development lane: use the GPU pod to benchmark Gemma, design prompts, create calibration data, test verifier rubrics and produce the Best Use of Gemma story.
3. Small local lane: test Gemma E2B-class 4-bit inference inside the final CPU/RAM envelope.
4. Fine-tuning / distillation lane: fine-tune or distill behavior only if the output path remains compatible with `ALLOWED_MODELS` or produces a compact final component that fits the official environment.

Do not assume that a Fireworks Model Library page marked `Deploy on Demand` is automatically valid for Track 1 scoring. A dedicated deployment can be useful for experiments, but the final route must still comply with `FIREWORKS_BASE_URL` and `ALLOWED_MODELS`.

## Role Of Mechanical Code

Mechanical code is still valid, but it should not be the identity of the project.

Correct framing:

- schema validation;
- output cleaning;
- JSON repair;
- timeout protection;
- exact arithmetic when the task is structurally unambiguous;
- final answer format checks;
- model-risk signals for routing.

Incorrect framing:

- replacing the general-purpose AI agent with broad regex rules;
- hardcoding answer patterns from examples;
- turning all eight categories into brittle handcrafted translations;
- presenting deterministic solvers as the core intelligence.

The narrative should be: AI routing agent first, mechanical safety layer second.

## Championship Architecture After The Correction

The safe official default is:

```text
/input/tasks.json
-> parse and normalize task envelope
-> mechanical validators for schema, format and high-confidence calculations
-> Fireworks model router reads ALLOWED_MODELS
-> choose cheapest sufficient model by category/risk/matrix weights
-> compact prompt, short answer, strict output cleaning
-> /output/results.json
```

The experimental local-first candidate is:

```text
/input/tasks.json
-> compact local model <= 2B-3B 4-bit, if proven under 4 GB RAM / 2 vCPU
-> local semantic triage or draft answer
-> mechanical verifier
-> escalate uncertain tasks to Fireworks ALLOWED_MODELS
-> /output/results.json
```

Gemma 26B/31B belongs in:

```text
AMD pod / Fireworks allowed route / demo / calibration / fine-tuning research
```

not in:

```text
final Docker image as bundled local weights
```

## Current Decision

- Keep Docker default as `ROUTER_MODE=fireworks`.
- Keep `ROUTER_MODE=hybrid` for lab work and promote it only if a compact local model, ideally small Gemma, passes the final envelope.
- Keep Gemma support in routing logic, tags, docs and calibration.
- Do not create or depend on an on-demand Gemma deployment in the final judged path unless organizers confirm it appears in `ALLOWED_MODELS` and is counted correctly.
- Reframe deterministic solvers as mechanical validators and not the heart of the agent.

## Immediate Next Work

- Calibrate the Fireworks router against the actual `ALLOWED_MODELS` injected by the harness.
- Test Gemma access through the official `FIREWORKS_BASE_URL` when available.
- Explore small Gemma as a local semantic triage/verifier only if it can fit `4 GB` RAM and improves token count without harming accuracy.
- Update pitch materials to emphasize general-purpose routing, Gemma readiness and Fireworks model selection.
- Keep every final submission path reproducible without private `.env` files or hardcoded model IDs.
