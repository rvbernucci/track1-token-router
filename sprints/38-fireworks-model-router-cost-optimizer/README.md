# Sprint 38 - Fireworks Model Router Cost Optimizer

## Type

Does not depend on credits.

## Objective

Adapt the project to the official Track 1 clarification: the main game is choosing, in real-time, the cheapest Fireworks model that should still pass the accuracy gate.

Local models remain useful for development, offline evaluation, and calibration, but the final path needs to route Fireworks calls through `FIREWORKS_BASE_URL` using only models from `ALLOWED_MODELS`.

## Thesis

The winner is not the one who avoids Fireworks at all costs. The winner is the one who chooses the smallest sufficient Fireworks model for each task.

## Deliverables

- Fireworks model router based on `ALLOWED_MODELS`.
- Heuristic ranking of cost/capability by model name/size.
- Selector by task type: cheap, medium, strong.
- Metadata with `fireworks_model_selection`.
- Tests for ranking and selection.
- Integration with `ROUTER_MODE=fireworks`.

## Checklist

- [x] Create `router/orchestration/fireworks_model_router.py`.
- [x] Implement ranking by model size/keyword.
- [x] Implement cheap/medium/strong selection.
- [x] Use selected model in the OpenAI-compatible payload.
- [x] Record selection in metadata.
- [x] Preserve deterministic solvers before Fireworks.
- [x] Add ranking tests.
- [x] Add category selection tests.
- [x] Add test ensuring payload uses the selected model.
- [ ] Calibrate against actual `ALLOWED_MODELS` when released.
- [ ] Add actual cost table if the organization publishes prices/models.
- [ ] Measure accuracy/token per tier when credits are available.

## Official Categories and Initial Tier

- Sentiment classification: `cheap`.
- Strict formatting/simple extraction: `cheap`.
- Text summarisation: `medium`.
- Named entity recognition: `medium`.
- Factual knowledge: `medium` or `strong` if current/specific.
- Mathematical reasoning: `strong` when multi-step.
- Logical / deductive reasoning: `strong`.
- Code debugging/generation: `strong`.

## Risks

- Model name not reflecting real cost.
- Cheap model passing low tokens but failing accuracy gate.
- Strong model being overused and hurting token ranking.
- The single prompt not being optimized per tier.

## Definition of Done

- The official path does not always choose the first model.
- Model choice is auditable per task.
- Strategy can be recalibrated without changing the Docker contract.
