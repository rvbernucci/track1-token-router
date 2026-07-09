# Local Model Scoring Strategy

## Current Reading

Track 1 allows local models as a scoring strategy. A local answer produced inside the container counts toward accuracy, and local inference contributes zero Fireworks tokens. This makes local-first routing the best theoretical strategy when local quality and latency are good enough.

The latest Track 1 guide adds a hard practical limit: final grading runs with `4 GB` RAM and `2 vCPU`. It explicitly says `2B-3B` 4-bit quantized local models are safe, while `7B` 4-bit can consume the whole RAM budget. Therefore Gemma 26B/31B should not be treated as a local model inside the final submitted image.

The AMD/Gemma partner wording still matters, but its role is different:

- AMD GPU pod: development, calibration, prompt design, fine-tuning experiments and Gemma demo lane;
- Fireworks: judged remote path through `FIREWORKS_BASE_URL` and `ALLOWED_MODELS`;
- final local inference: only compact models that fit the grading envelope;
- code validators: mechanical safety checks around the agent, not a substitute for the AI agent.

## Two Final Modes

### Safe Mode: Fireworks Direct

Use when there is no reliable compact local model inside the submitted container, or when the local model cannot meet the accuracy/latency envelope.

```bash
ROUTER_MODE=fireworks
```

Properties:

- mechanical validators and narrowly safe solvers run before Fireworks;
- every non-solved task goes to the cheapest sufficient allowed Fireworks model;
- robust in the official `4 GB` RAM / `2 vCPU` grading environment;
- not maximally token-efficient if local model quality would have been sufficient.

### Championship Mode: Local-First Hybrid

Use only when a compact local model endpoint is available inside the final container, or when the official harness explicitly provides an endpoint alongside the container.

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
- not a Gemma 26B/31B plan for final scoring unless the organizers explicitly provide that endpoint.

## Practical Constraint

Local-first only wins if all of these are true:

- the model server starts within the container/startup budget;
- per-task latency stays under the Track 1 limit;
- local answers clear the accuracy gate;
- the Docker image remains below the size cap;
- the local model can be served reliably inside the final `4 GB` RAM / `2 vCPU` environment, or is explicitly provided by the harness.

## Current Project Decision

- Keep Docker default as `ROUTER_MODE=fireworks`.
- Treat `ROUTER_MODE=hybrid` as an experimental/championship candidate only after a compact local model is proven under the final resource envelope.
- Treat Gemma-on-AMD-pod as the primary research/demo/fine-tuning lane for the Best Use of Gemma story, not as an assumed final local runtime.
- Keep mechanical validators enabled in both paths, but describe them as safety/economy layers around the AI agent.
- Use Fireworks as the authoritative final remote path whenever the local compact path is not proven.

## AMD Pod Action

Team registration is required before GPU access. Even solo participants must create or join a lablab.ai team. After registration, resource allocation can take up to 24 hours, and pod usage is limited to 8 hours per 24 hours.

Once access is active:

- open `https://notebooks.amd.com/hackathon`;
- confirm the team pod is allocated;
- start a local OpenAI-compatible Gemma endpoint with vLLM or SGLang;
- point `LOCAL_BASE_URL` and `LOCAL_MODEL` to that endpoint;
- run local, cascade and hybrid evals to understand Gemma behavior;
- distill the result into prompts, routing thresholds, verifier rubrics or a compact local model that can actually fit the final container.

## Next Calibration

When AMD GPU pod access is active:

1. Start a local OpenAI-compatible server.
2. Run `ROUTER_MODE=local` smoke tests.
3. Run `ROUTER_MODE=cascade` on the 8-category eval.
4. Run `ROUTER_MODE=hybrid` with Fireworks fallback.
5. Compare accuracy, latency and Fireworks token count against `ROUTER_MODE=fireworks`.
6. Decide whether any local component can be moved into final scoring without violating the `4 GB` RAM / `2 vCPU` limit.
