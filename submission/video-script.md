# Video Script

Target length: 4 to 5 minutes.

## 0:00 - Hook

Track 1 is not won by calling the strongest model every time. It is won by knowing when not to call it. Track 1 Token Router is a local-first routing agent that spends remote Fireworks tokens only when local confidence breaks.

## 0:30 - Problem

The official evaluator can send broad tasks, strict formats and unexpected input shapes. A naive system either wastes remote tokens or returns cheap wrong answers. We need accuracy and token discipline at the same time.

## 1:00 - Architecture

The runner receives a `TaskEnvelope` and first checks deterministic paths: guardrails and solvers. If code can answer safely, the model is skipped. Otherwise M1 generates a local candidate. M2A verifies it locally. If confidence is high, the answer returns with zero remote tokens. If risk is high, M2B creates a local repair and Fireworks audits a compact packet in approve-or-replace mode.

## 2:00 - Competition Mode

`ROUTER_MODE=competition` integrates guardrails, deterministic solvers, risk signals, budget policy, prompt packet estimation, final validation and state traces. It runs in dry-run mode without credits, so the team can test the full path before AMD or Fireworks access is active.

## 2:45 - Demo

Run:

```bash
ROUTER_MODE=competition COMPETITION_DRY_RUN=1 python3 -m router ask "What is 6 * 7? Return only the number." --json
```

The route is `solver_arithmetic`, answer is `42`, and remote tokens are zero. Then run the battle drill:

```bash
scripts/battle_drill.py
```

The report checks policy score, competition readiness, solver savings, fuzz input robustness and runtime profile readiness.

Then show one readable replay:

```bash
python3 scripts/replay_decision.py --text "Who is the CEO of AMD today?"
```

This exposes risk signals, budget decision, policy decision and final validation. The contrast is the point: arithmetic stays deterministic, current knowledge becomes a remote-audit candidate in dry-run.

## 3:45 - Readiness

The repo includes Docker, CI, offline release checks, fuzz tests, runtime profiles for AMD MI300X with vLLM or SGLang, Gemma runbooks and Fireworks activation steps. This makes credits an activation step, not a blocker.

## 4:30 - Close

The thesis is simple: use local intelligence by default, deterministic code when possible, and remote power only when it materially improves correctness. That is how we chase high accuracy with low remote token spend.
