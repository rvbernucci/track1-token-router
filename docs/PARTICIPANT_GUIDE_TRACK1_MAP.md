# Participant Guide Track 1 Map

Source: `Participant Guide: AMD Developer Hackathon (ACT II)`, attached PDF.

## Confirmed Track 1 Contract

Track 1 is now described as a general-purpose AI agent benchmark. Exact evaluation inputs are intentionally omitted and hidden variants are used.

Update from the Track 1 page shared on 2026-07-08: final scoring rewards routing intelligence across Fireworks models and local inference. Local models are a valid scoring strategy: answers produced by local models inside the container count fully toward accuracy, while only calls routed through `FIREWORKS_BASE_URL` count toward the Fireworks token score. Local inference therefore has zero Fireworks-token cost.

Update from the Track 1 guide shared on 2026-07-08: Track 1 is constrained to this model set:

- `minimax-m3`;
- `kimi-k2p7-code`;
- `gemma-4-31b-it`;
- `gemma-4-26b-a4b-it`;
- `gemma-4-31b-it-nvfp4`.

The router accepts both these short names and full Fireworks IDs like `accounts/fireworks/models/minimax-m3`.

The container must:

- read tasks from `/input/tasks.json` on startup;
- write results to `/output/results.json` before exiting;
- exit `0` on success and non-zero on failure;
- produce valid JSON output;
- be publicly pullable;
- include a `linux/amd64` image manifest;
- start and be ready within 60 seconds;
- keep response time per request under 30 seconds;
- finish within a maximum runtime of 10 minutes;
- answer in English.

GPU/team access:

- participants must create or join a lablab.ai team, even when competing solo;
- one AMD GPU pod is assigned per registered team;
- allocation can take up to 24 hours after team registration;
- GPU pod usage is limited to 8 hours per 24 hours per team;
- `team not registered` on `notebooks.amd.com/hackathon` means the team step is missing.

Input format:

```json
[
  {
    "task_id": "t1",
    "prompt": "Summarise the following text in one sentence: ..."
  }
]
```

Output format:

```json
[
  {
    "task_id": "t1",
    "answer": "..."
  }
]
```

## Environment Variables

The harness injects:

- `FIREWORKS_API_KEY`;
- `FIREWORKS_BASE_URL`;
- `ALLOWED_MODELS`.

Rules:

- use the harness key, not a private key;
- route all Fireworks calls through `FIREWORKS_BASE_URL`;
- read permitted model IDs from `ALLOWED_MODELS` at runtime;
- do not bundle `.env` in the image;
- do not hardcode model IDs.

Important implication: calls that bypass `FIREWORKS_BASE_URL` will not be recorded and score zero tokens.

Important correction: local model calls do not bypass scoring for accuracy. They bypass only Fireworks token accounting. If a local model answer is correct, it counts for the accuracy gate and costs zero Fireworks tokens.

## Fireworks Access Modes

The Fireworks Model Library, Batch Inference UI and Deployments UI expose different access modes.

Official partner statement:

- Gemma is available to participants through AMD Developer Cloud and Fireworks AI.
- Gemma can be used in routing, captioning and agent workflows.
- Track 1 has a specific partner prize: Best Use of Gemma via Fireworks.
- The same official page says model restrictions vary by track, so choices must be checked against Track 1 requirements.

Current practical interpretation:

- Gemma on the AMD GPU pod is the strongest local-first path and supports the Best Use of Gemma narrative.
- Gemma through Fireworks serverless is still not accessible with the current local credit key.
- Fireworks remains necessary as fallback/router path through `FIREWORKS_BASE_URL`.

For Track 1 final scoring, the safe interpretation is:

- use only the models injected through `ALLOWED_MODELS`;
- call them through the injected `FIREWORKS_BASE_URL`;
- do not assume a model visible in the Model Library is serverless or allowed.

Observed Gemma status on 2026-07-07:

- `accounts/fireworks/models/gemma-4-31b-it` exists in the Model Library;
- it is marked `Deploy on Demand`;
- it is marked `Serverless: Not supported`;
- direct serverless chat completion returns `Model not found, inaccessible, and/or not deployed` without a dedicated deployment or special access.

Rechecked on 2026-07-08 after receiving Fireworks credits:

- direct serverless smoke for `accounts/fireworks/models/gemma-4-31b-it` still returns `HTTP 404 Not Found`;
- direct serverless smoke for `accounts/fireworks/models/gemma-4-26b-a4b-it` and `accounts/fireworks/models/gemma-4-31b-it-nvfp4` also returns `HTTP 404 Not Found`;
- Fireworks public model pages still show Gemma models as on-demand rather than serverless;
- the API key can call official allowed serverless models `minimax-m3` and `kimi-k2p7-code`, so this is a Gemma access/path issue, not a general key failure.

Implication: Gemma is official for Track 1, but our current Fireworks credit key does not expose it through serverless. The competition router must remain `ALLOWED_MODELS`-first and must gracefully fall back if one allowed model is inaccessible in a given environment.

Practical strategy:

- Use Gemma-first only for cheap/medium language tasks: classification, formatting, summarization and extraction.
- Use `minimax-m3` first for strong math, logic, code debugging and code generation because it is accessible and benchmarked.
- Keep `kimi-k2p7-code` as an allowed fallback/candidate for code and logic, but do not make it default on current evidence because it is slower and more expensive.
- If Gemma is not accessible in local Fireworks credits, fallback to `minimax-m3` without failing the run.
- Do not create a paid on-demand Gemma deployment inside the final Track 1 path unless the organizers explicitly confirm it is allowed and counted.

On-Demand Deployment note:

- Fireworks On-Demand can likely make Gemma callable through a dedicated deployment.
- That is useful for calibration, demo and Gemma partner narrative.
- It is not automatically safe for final Track 1 scoring because deployment IDs may not match `ALLOWED_MODELS`, may not be token-scored the same way, and may create GPU-second cost.
- Treat On-Demand Gemma as a separate lane until the organizers confirm it is allowed inside the judged route.

## Scoring

Scoring is two-stage:

1. Accuracy gate: an LLM judge evaluates each answer against expected intent. Submissions below threshold are excluded from the leaderboard.
2. Token efficiency: among submissions passing the gate, ranking is ascending by total tokens recorded by the judging proxy.

Confirmed:

- local models and local tokens count as zero for final score;
- local model answers count fully toward the accuracy gate;
- all Fireworks inference must go through `FIREWORKS_BASE_URL`;
- malformed `/output/results.json` scores zero;
- hardcoded or cached answers are prohibited;
- only models in `ALLOWED_MODELS` are permitted;
- submissions are rate-limited to 10 per hour per team;
- compressed image size must not exceed 10GB.

## Capability Categories

The agent is evaluated across eight categories:

- factual knowledge;
- mathematical reasoning;
- sentiment classification;
- text summarisation;
- named entity recognition;
- code debugging;
- logical / deductive reasoning;
- code generation.

## Project Implications

Immediate implications:

- exact official adapter is required now, not at kickoff;
- Docker default command should implement `/input/tasks.json` to `/output/results.json`;
- `linux/amd64` build path must be documented and tested;
- timeout and per-request latency are hard constraints;
- M2A/mechanical validation must cover all eight categories, not only math and format;
- Fireworks client must prefer `ALLOWED_MODELS` rather than a hardcoded model when in official mode;
- official mode must choose the cheapest sufficient Fireworks model per task, not always the first allowed model;
- logs must not pollute stdout or output JSON.

## Implemented Local Mapping

- Adapter: `router/adapters/official/lablab_track1.py`
- Fixture: `fixtures/official/lablab_track1_tasks.json`
- CLI: `router submit-track1 --input /input/tasks.json --output /output/results.json`
- Docker default command: `router submit-track1`
- Docker default mode: `ROUTER_MODE=fireworks`
- Model router: ranks `ALLOWED_MODELS` and selects cheap/medium/strong per task
- CI smoke test: mounted `/input` and `/output` with valid JSON output

## Remaining Work

- Add timeout budget around per-task execution.
- Extend mechanical validation fixtures to all eight official categories.
- Calibrate model tiers against the real `ALLOWED_MODELS` list when available.
