# Gemma Small Local Strategy

Updated: 2026-07-09

## Decision

Yes: we should investigate a small local Gemma path for Track 1.

The latest Track 1 guide explicitly says local models are permitted and that `2B-3B` 4-bit quantized models are safe candidates for the final `4 GB` RAM / `2 vCPU` grading environment. The attached Gemma material also shows Gemma 4 small models, including E2B and E4B, with local/on-device deployment as a core design goal.

The correction is narrow:

- Gemma 26B/31B: AMD pod, Fireworks allowed route, calibration and demo.
- Gemma 4 E2B or similarly small Gemma: possible final-container local model candidate.
- Gemma 4 E4B: likely too large for the final envelope unless a mobile/text-only runtime proves otherwise.

## Why This Matters

Remote Fireworks tokens are the ranking cost after the accuracy gate. If a small local model can correctly handle even a fraction of easy and medium tasks, it can improve ranking without spending Fireworks tokens.

This also strengthens the Gemma partner story:

- the project uses Gemma inside the agent workflow;
- Gemma is not only a slide/demo artifact;
- Gemma becomes part of the token-efficiency mechanism.

## Candidate Order

| Candidate | Fit | Risk | Initial Role |
|---|---|---|---|
| Gemma 4 E2B QAT / 4-bit local | Best serious Gemma candidate for final Docker | Tight memory once runtime, Python and KV cache are included | M2A verifier, triage classifier, short-answer draft |
| Gemma 4 E2B mobile/text-only | Best memory profile if tooling is viable | Integration risk and runtime dependency risk | M2A verifier or classifier |
| Previous small Gemma 2B/3B family | Good fallback if Gemma 4 tooling is heavy | Weaker partner narrative than Gemma 4 | Triage/verifier |
| Gemma 4 E4B QAT / 4-bit | Stronger quality | Likely over `4 GB` with overhead | AMD pod only until proven |
| Gemma 26B/31B | Strong quality | Does not fit final CPU/RAM envelope | AMD pod / Fireworks only |

## Correct Role In The Agent

Small Gemma should not be asked to solve everything.

Best initial role:

```text
prompt
-> mechanical validator
-> small Gemma M2A triage/verifier
-> approve only if task is easy and answer format is safe
-> otherwise route to Fireworks ALLOWED_MODELS
```

Possible second role after validation:

```text
prompt
-> small Gemma M1 short candidate
-> small Gemma M2A strict verifier
-> Fireworks if verifier is uncertain
```

Avoid:

- using small Gemma as the only responder for all eight categories;
- allowing long outputs from local model;
- large context windows in final grading;
- multimodal/audio paths unless the official evaluator actually sends those inputs;
- loading both a local LLM server and heavy Python dependencies if memory exceeds budget.

## Memory And Runtime Gates

Before promoting small Gemma to final scoring, all gates must pass inside a Docker run constrained to the official envelope:

```bash
docker run --rm --memory=4g --cpus=2 ...
```

Before downloading or bundling a model, estimate the envelope:

```bash
python3 scripts/local_model_envelope.py \
  --model-size-mb 2900 \
  --runtime-overhead-mb 400 \
  --kv-cache-mb 256 \
  --safety-margin-mb 384 \
  --check
```

If this fails, the model is not a final-container candidate unless the runtime overhead or KV cache assumptions are proven too conservative.

Hard gates:

- container starts fast enough for the evaluator;
- model load succeeds under `4 GB` RAM;
- steady-state RSS leaves at least `384 MB` safety margin;
- p95 task latency stays below the official per-task budget;
- total run finishes under 10 minutes;
- image compressed size remains below `10 GB`;
- accuracy is not worse than `ROUTER_MODE=fireworks` on the eight-category eval;
- Fireworks token count drops enough to justify the local complexity.

Recommended first settings:

- context window: `512-2048` tokens;
- local max output: `64-128` tokens for verifier/triage;
- temperature: `0.0`;
- role: JSON classifier/verifier before free-form answer generation;
- fallback: Fireworks on uncertainty.

## Champion / Challenger Policy

Keep two images or modes until measured:

- Champion: `ROUTER_MODE=fireworks`, no bundled local model.
- Challenger: `ROUTER_MODE=hybrid`, small Gemma local verifier/draft.

Promote challenger only if it beats champion on:

- accuracy gate;
- total Fireworks tokens;
- runtime stability;
- memory envelope;
- submission simplicity.

## Implementation Plan

1. Keep current Fireworks image as the safe default.
2. Add a small-Gemma runtime profile with strict memory-oriented defaults.
3. Build a local-model envelope test that runs under `--memory=4g --cpus=2`.
4. Try Gemma E2B 4-bit as verifier first, not universal responder.
5. Compare against Fireworks-only on the official eight-category practice/eval packs.
6. If the challenger wins, document the Docker image and submit that variant.

## Current Conclusion

Small local Gemma is now a serious candidate, but not yet the default.

The best next sprint is not "replace Fireworks with Gemma". It is:

```text
prove whether Gemma E2B-class local inference can safely remove enough Fireworks calls
without failing accuracy or the 4 GB / 2 vCPU grading envelope.
```
