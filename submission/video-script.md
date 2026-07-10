# Video Script

Target length: 4 to 5 minutes.

## 0:00 - Hook

Track 1 is not won by calling the strongest model every time. It is won by knowing which model is sufficient. Track 1 Token Router is a general-purpose routing agent that spends Fireworks tokens only when the expected accuracy gain justifies the cost.

## 0:30 - Problem

The official evaluator can send broad tasks, strict formats and unexpected input shapes. A naive system either wastes remote tokens or returns cheap wrong answers. We need accuracy and token discipline at the same time.

## 1:00 - Architecture

The runner receives a `TaskEnvelope`. A registered solver can answer only when it proves an exact mechanical contract. Everything else goes to Kimi K2.7 Code when the evaluator authorizes it in `ALLOWED_MODELS`. Dynamic completion ceilings reduce output waste; strict validators repair only unambiguous formatting and retry another allowed model when necessary.

We did not arrive here by assumption. We trained FunctionGemma 270M on the AMD pod and tested Gemma 4 E2B locally across 2,000 tasks. E2B fit memory, but its selected locked-test region reached only 51.14% accuracy. We rejected it rather than optimize the story instead of the score.

## 2:00 - Competition Mode

`ROUTER_MODE=fireworks` implements the official path. The champion preference is still constrained by `ALLOWED_MODELS`, and every request goes through `FIREWORKS_BASE_URL`. Structured traces record route, selected model, tokens, validation and fallback without exposing credentials.

## 2:45 - Demo

Run:

```bash
ROUTER_MODE=competition COMPETITION_DRY_RUN=1 python3 -m router ask "What is 6 * 7? Return only the number." --json
```

The route is a mechanical arithmetic validator, answer is `42`, and remote tokens are zero. Then run the battle drill:

```bash
scripts/battle_drill.py
```

The report checks policy score, competition readiness, solver savings, fuzz input robustness and runtime profile readiness.

Then show one readable replay:

```bash
python3 scripts/replay_decision.py --text "Who is the CEO of AMD today?"
```

This exposes risk signals, budget decision, policy decision and final validation. The contrast is the point: mechanical cases stay safe and cheap, while open-ended knowledge becomes a model-routing decision.

## 3:45 - Readiness

The repo includes Docker, CI, offline release checks, adversarial routing tests, FunctionGemma training evidence, E2B rejection evidence and a 571-task Fireworks ablation. CI tests the exact Linux `amd64` image under 4 GB RAM, 2 vCPU, no network and the official input/output contract.

## 4:30 - Close

The thesis is simple: accuracy first, tokens second, and evidence before complexity. We kept the zero-token solver path, promoted Kimi only when allowed, and removed every architecture that did not survive the holdout.
