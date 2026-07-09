# Video Script

Target length: 4 to 5 minutes.

## 0:00 - Hook

Track 1 is not won by calling the strongest model every time. It is won by knowing which model is sufficient. Track 1 Token Router is a general-purpose routing agent that spends Fireworks tokens only when the expected accuracy gain justifies the cost.

## 0:30 - Problem

The official evaluator can send broad tasks, strict formats and unexpected input shapes. A naive system either wastes remote tokens or returns cheap wrong answers. We need accuracy and token discipline at the same time.

## 1:00 - Architecture

The runner receives a `TaskEnvelope` and first applies mechanical validators: schema checks, output constraints, high-confidence arithmetic and format safety. Then the router reads `ALLOWED_MODELS`, estimates category and risk, and chooses the cheapest sufficient Fireworks model. A compact local model can be added only if it fits the official `4 GB` RAM and `2 vCPU` grading envelope.

## 2:00 - Competition Mode

`ROUTER_MODE=competition` integrates validators, risk signals, budget policy, prompt packet estimation, final validation and state traces. It runs in dry-run mode without credits, so the team can test the full path before AMD or Fireworks access is active.

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

The repo includes Docker, CI, offline release checks, fuzz tests, Fireworks calibration, Gemma runbooks and AMD pod profiles for development. The final image remains small enough for the official CPU/RAM grading environment.

## 4:30 - Close

The thesis is simple: use model intelligence deliberately, keep prompts compact, validate mechanically where it is safe, and route to the smallest sufficient Fireworks model. That is how we chase high accuracy with low token spend.
