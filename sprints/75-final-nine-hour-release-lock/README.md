# Sprint 75 - Final Release Lock

## Timebox

`150 minutes`, followed by a protected `30-minute` submission and rollback reserve.

## Objective

Integrate only evidence-backed Sprint 71-74 changes, publish one immutable `linux/amd64` image and preserve `v3.6.0-category-calibrated` as a one-field rollback.

## Integration

- [x] Retain the hash-pinned scale-789 Q8 assessor after semantic-v3 Q8 failed the frozen non-inferiority gate.
- [x] Exclude cluster geometry after Sprint 72 failed protected calibration gates.
- [x] Embed the Wilson-Nash ladder as a versioned, hash-pinned policy.
- [x] Keep verify-or-repair disabled after every tested stratum failed the token/support gate.
- [x] Preserve the prompt-envelope boundary: parse `task_id` and `prompt` in code, then send only the raw prompt text to E2B or direct Fireworks.
- [x] Keep routing features, cluster IDs, regression scores, Wilson bounds, Nash utilities and the official JSON envelope out of answer-generation prompts.
- [x] Preserve the compact untrusted-data reviewer protocol in code while leaving the rejected route disabled.
- [x] Keep model answers as free-form strings unless the task itself explicitly requests structured output.
- [x] Run the Answer Contract Engine after every route and reconstruct `{"task_id":"...","answer":"..."}` exclusively in code.
- [x] Keep all experimental libraries, training data and teacher ledgers outside the Docker image.
- [x] Keep runtime free of `scikit-learn`, HDBSCAN and training dependencies.
- [x] Preserve deterministic proof, Answer Contract Engine and dynamic `ALLOWED_MODELS` behavior.

## Verification

- [x] Run the complete unit and integration suite: 679 pass, one environment-dependent skip.
- [x] Run contract, secret, provenance and reproducibility checks.
- [x] Run exact input `/input/tasks.json` to `/output/results.json` validation.
- [x] Assert that E2B and direct Fireworks request captures contain the raw prompt but no `task_id`, adapter metadata or routing internals.
- [x] Assert byte-valid deterministic reconstruction of every output item after contract validation.
- [x] Run the image with `4 GB RAM`, `2 vCPU`, `linux/amd64`, no network and a `600 s` limit.
- [x] Measure cold start, warm latency and peak memory in exact-image run `29196742441`.
- [x] Confirm no startup downloads and no bundled credentials.
- [x] Confirm compressed image size remains below `10 GB`.
- [x] Confirm public clean pull and `linux/amd64` manifest.
- [x] Replay Fireworks authorization with reordered and reduced `ALLOWED_MODELS`.

## Documentation

- [x] Update README, architecture, evaluator assumptions and public scorecards in English.
- [x] Separate measured claims from projections and experimental results.
- [x] Document the Wilson confidence level and lower-bound ladder unambiguously.
- [x] Document cluster training as an offline rejected challenger with no runtime dependency.
- [x] Document verify-or-repair as one Fireworks call, never a two-call cascade.
- [x] Document the prompt-envelope boundary as a token-efficiency and answer-quality invariant.
- [x] Record artifact, policy, source, image and platform digests.

## Release Decision

- [x] Promote only the Wilson-Nash guard; reject all challengers that failed accuracy or token gates.
- [x] Tag and push one immutable championship image.
- [x] Perform a clean public pull and repeat the exact-image audit.
- [ ] Update the lablab.ai Docker field only after the public audit succeeds.
- [x] Keep `ghcr.io/rvbernucci/track1-token-router:v3.6.0-category-calibrated` documented as rollback.
- [x] Freeze architecture changes after release; permit only evidence or documentation corrections.

## Definition of Done

- [x] Repository, Docker image, submission text and measured evidence agree exactly.
- [x] The evaluator can run the image with injected environment variables and no manual setup.
- [x] More than `45 minutes` remain for manual submission verification or rollback.

## Final Evidence

- Image: `ghcr.io/rvbernucci/track1-token-router:v3.7.0-wilson-nash`
- Release run: `29196181749`
- Exact-image local-inference run: `29196742441`
- Source revision: `2b76451f885ff36e8874f212779a36c7f539e0c0`
- Manifest: `sha256:3b661e9abf9f491d8f63ee941b218ba8269b6cd82c09d897723167f0c6513620`
- Platform: `sha256:cc53eb3cebe712073c28cc9f2f00acd466065fcf9df32a9fe9e8ff39773ae2b2`
- Exact local gate: two E2B routes, zero Fireworks tokens, cold `9.48 s`, warm `1.447 s`, sampled peak `639.8 MiB`.
