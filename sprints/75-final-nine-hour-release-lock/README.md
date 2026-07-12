# Sprint 75 - Final Release Lock

## Timebox

`150 minutes`, followed by a protected `30-minute` submission and rollback reserve.

## Objective

Integrate only evidence-backed Sprint 71-74 changes, publish one immutable `linux/amd64` image and preserve `v3.6.0-category-calibrated` as a one-field rollback.

## Integration

- [ ] Replace FunctionGemma only with the hash-pinned Q8 champion from Sprint 71.
- [ ] Embed cluster geometry only if Sprint 72 passes protected gates.
- [ ] Embed the Wilson-Nash ladder as a versioned, hash-pinned policy.
- [ ] Enable verify-or-repair only for Sprint 74 strata that beat direct Fireworks.
- [ ] Preserve the prompt-envelope boundary: parse `task_id` and `prompt` in code, then send only the raw prompt text to E2B or direct Fireworks.
- [ ] Keep routing features, cluster IDs, regression scores, Wilson bounds, Nash utilities and the official JSON envelope out of answer-generation prompts.
- [ ] For verify-or-repair only, send the raw prompt plus the candidate answer in a compact untrusted-data envelope; never send the official task JSON.
- [ ] Keep model answers as free-form strings unless the task itself explicitly requests structured output.
- [ ] Run the Answer Contract Engine after every route and reconstruct `{"task_id":"...","answer":"..."}` exclusively in code.
- [ ] Keep all experimental libraries, training data and teacher ledgers outside the Docker image.
- [ ] Keep runtime free of `scikit-learn`, HDBSCAN and training dependencies.
- [ ] Preserve deterministic proof, Answer Contract Engine and dynamic `ALLOWED_MODELS` behavior.

## Verification

- [ ] Run the complete unit and integration suite.
- [ ] Run contract, secret, provenance and reproducibility checks.
- [ ] Run exact input `/input/tasks.json` to `/output/results.json` validation.
- [ ] Assert that E2B and direct Fireworks request captures contain the raw prompt but no `task_id`, adapter metadata or routing internals.
- [ ] Assert byte-valid deterministic reconstruction of every output item after contract validation.
- [ ] Run the image with `4 GB RAM`, `2 vCPU`, `linux/amd64`, no network and a `600 s` limit.
- [ ] Measure cold start, warm latency, peak memory and batch deadline reserve.
- [ ] Confirm no startup downloads and no bundled credentials.
- [ ] Confirm compressed image size remains below `10 GB`.
- [ ] Confirm public anonymous pull and manifest platform.
- [ ] Replay Fireworks authorization with reordered and reduced `ALLOWED_MODELS`.

## Documentation

- [ ] Update README, architecture, model card, evaluator assumptions and public scorecard in English.
- [ ] Separate measured claims from projections and experimental results.
- [ ] Document the Wilson confidence level and lower-bound ladder unambiguously.
- [ ] Document cluster training as offline and centroid evaluation as runtime-only.
- [ ] Document verify-or-repair as one Fireworks call, never a two-call cascade.
- [ ] Document the prompt-envelope boundary as a token-efficiency and answer-quality invariant.
- [ ] Record artifact, policy, source, image and platform digests.

## Release Decision

- [ ] Promote only if accuracy-first gates, token economics and official resource gates all pass.
- [ ] Tag and push one immutable championship image.
- [ ] Perform a clean public pull and repeat the exact-image audit.
- [ ] Update the lablab.ai Docker field only after the public audit succeeds.
- [ ] Keep `ghcr.io/rvbernucci/track1-token-router:v3.6.0-category-calibrated` documented as rollback.
- [ ] Freeze architecture changes after release; permit only evidence or documentation corrections.

## Definition of Done

- [ ] Repository, Docker image, submission text and measured evidence agree exactly.
- [ ] The evaluator can run the image with injected environment variables and no manual setup.
- [ ] At least `45 minutes` remain for submission verification or rollback.
