# Local Model Scoring Strategy

## Current Reading

Track 1 allows local models as a scoring strategy. A local answer produced inside the container counts toward accuracy, and local inference contributes zero Fireworks tokens. This makes local-first routing the best theoretical strategy when local quality and latency are good enough.

## Two Final Modes

### Safe Mode: Fireworks Direct

Use when there is no reliable local model endpoint in the judging environment.

```bash
ROUTER_MODE=fireworks
```

Properties:

- deterministic solvers run before Fireworks;
- every non-solved task goes to the cheapest sufficient allowed Fireworks model;
- robust when local GPU/model serving is unavailable;
- not maximally token-efficient if local model quality would have been sufficient.

### Championship Mode: Local-First Hybrid

Use when a local OpenAI-compatible model endpoint is available inside or alongside the container.

```bash
ROUTER_MODE=hybrid
LOCAL_BASE_URL=http://127.0.0.1:8000/v1
LOCAL_MODEL=<local-served-model>
```

Properties:

- M1 generates a local candidate answer;
- M2A validates locally;
- approved answers return with zero Fireworks tokens;
- escalated answers use M2B locally before a compact Fireworks audit;
- best ranking potential if the local model is accurate enough within latency limits.

## Practical Constraint

Local-first only wins if all of these are true:

- the model server starts within the container/startup budget;
- per-task latency stays under the Track 1 limit;
- local answers clear the accuracy gate;
- the Docker image remains below the size cap;
- the local model can be served reliably on the AMD GPU pod or final environment.

## Current Project Decision

- Keep Docker default as `ROUTER_MODE=fireworks` until local model serving is proven in the AMD pod.
- Use `ROUTER_MODE=hybrid` as the championship path once a local endpoint is stable.
- Keep deterministic solvers enabled in both paths.
- Use Fireworks as fallback, not as default, once local quality is validated.

## Next Calibration

When AMD GPU pod access is active:

1. Start a local OpenAI-compatible server.
2. Run `ROUTER_MODE=local` smoke tests.
3. Run `ROUTER_MODE=cascade` on the 8-category eval.
4. Run `ROUTER_MODE=hybrid` with Fireworks fallback.
5. Compare accuracy, latency and Fireworks token count against `ROUTER_MODE=fireworks`.
