# Participant Guide Track 1 Map

Source: `Participant Guide: AMD Developer Hackathon (ACT II)`, attached PDF.

## Confirmed Track 1 Contract

Track 1 is now described as a general-purpose AI agent benchmark. Exact evaluation inputs are intentionally omitted and hidden variants are used.

Update from the Track 1 page: final scoring rewards routing intelligence across Fireworks models. Local models are optional for development/testing and are not the core scoring path. Only inference routed through `FIREWORKS_BASE_URL` using a model from `ALLOWED_MODELS` is recorded for token scoring.

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

## Fireworks Access Modes

The Fireworks Model Library, Batch Inference UI and Deployments UI expose different access modes.

Official partner statement:

- Gemma is available to participants through AMD Developer Cloud and Fireworks AI.
- Gemma can be used in routing, captioning and agent workflows.
- Track 1 has a specific partner prize: Best Use of Gemma via Fireworks.
- The same official page says model restrictions vary by track, so choices must be checked against Track 1 requirements.

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
- Fireworks public model pages still show Gemma models as on-demand rather than serverless;
- the API key can call serverless models such as `deepseek-v4-flash`, so this is a Gemma access/path issue, not a general key failure.

Implication: Gemma is still valuable for the partner challenge, demos, calibration and possible on-demand deployment, but the competition router must remain `ALLOWED_MODELS`-first.

Practical strategy:

- If Gemma appears in `ALLOWED_MODELS`, make the router Gemma-first for tasks where Gemma is the cheapest sufficient model.
- If Gemma is not in `ALLOWED_MODELS`, keep the final scoring router compliant and use Gemma in documented development/calibration or an AMD-hosted companion demo.
- Do not create a paid on-demand Gemma deployment inside the final Track 1 path unless the organizers explicitly confirm it is allowed and counted.

## Scoring

Scoring is two-stage:

1. Accuracy gate: an LLM judge evaluates each answer against expected intent. Submissions below threshold are excluded from the leaderboard.
2. Token efficiency: among submissions passing the gate, ranking is ascending by total tokens recorded by the judging proxy.

Confirmed:

- local models and local tokens count as zero for final score;
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
