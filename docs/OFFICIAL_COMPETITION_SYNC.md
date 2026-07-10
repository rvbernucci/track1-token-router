# Official Competition Sync

Last checked: 2026-07-09

Source of truth: <https://lablab.ai/ai-hackathons/amd-developer-hackathon-act-ii> and the latest attached Track 1 participant guide excerpt.

## Track Choice

We are targeting Track 1: General-Purpose AI Agent / Hybrid Token-Efficient Routing Agent.

Official objective:

- complete fixed tasks autonomously;
- choose the cheapest sufficient Fireworks AI model when remote inference is needed;
- minimize Fireworks token usage without falling below the accuracy threshold;
- final scoring runs in a standardized environment.

## Current Strategic Implications

- Local models are a valid scoring strategy.
- Answers produced by local models inside the container count toward accuracy.
- Only tokens routed through `FIREWORKS_BASE_URL` count toward the token score.
- Local inference uses zero Fireworks tokens, so local-first routing is the strongest ranking path if quality is controlled.
- Prompt-based and fine-tuned approaches are scored the same way: token count and output accuracy.
- Final grading resource envelope is `4 GB` RAM and `2 vCPU`.
- A final local model must fit that envelope; the guide calls `2B-3B` 4-bit safe and warns that `7B` 4-bit can consume the whole RAM budget.
- Gemma 26B/31B should not be assumed as a local final-container model; use it through Fireworks when allowed, or in the AMD GPU pod for development/calibration/demo.
- Deterministic code should be framed as validation, formatting and mechanical safety around the agent, not as the primary AI capability.

## Submission Requirements

- All submissions must be containerized.
- The GitHub repository must be public.
- The repository must include setup and usage instructions.
- The application must be runnable using the provided instructions.
- The container must read `/input/tasks.json` on startup and write valid `/output/results.json` before exit.
- The container must finish within 10 minutes and exit `0` on success.
- The compressed image must stay below `10 GB` and include a `linux/amd64` manifest.
- The lablab.ai submission should include title, short description, long description, tags, cover image, video presentation, slide presentation, repository URL, demo platform, and application URL when applicable.

## Access And Credits

- Participants need an AMD AI Developer Program account for credits and resources.
- Teams must be created or joined on lablab.ai to receive access to an AMD GPU pod.
- The AMD GPU pod is assigned one per registered team.
- New AMD AI Developer Program members can claim AMD Developer Cloud credits and Fireworks AI credits through separate approval flows.

## Gemma Bonus

- Gemma is a named technology partner.
- Gemma can be used in routing, captioning, or agent workflows subject to track restrictions.
- Track 1 has a Best Use of Gemma via Fireworks partner prize.
- Gemma access is described as available through Fireworks AI and AMD Developer Cloud.

## Repository Alignment

- `Dockerfile` provides the container entrypoint for Track 1.
- `router submit-track1` implements the file contract used by the container default command.
- `ROUTER_MODE=fireworks` is the safest official default for the current final grading envelope.
- `ROUTER_MODE=three_route` reproduces the rejected FunctionGemma/E2B challenger; it is not the submitted default.
- `scripts/amd_pod_doctor.py` verifies the AMD pod before model downloads.
- `scripts/bootstrap_amd_pod.sh` validates clone-to-smoke bootstrap on the AMD notebook.
- `FIREWORKS_CHAMPION_MODEL` prefers validation-selected Kimi only when authorized by `ALLOWED_MODELS`.
- `FIREWORKS_MATRIX_WEIGHTS` remains a fallback experiment and cannot override the promoted champion.

## Watch Items

- If lablab.ai changes Track 1 scoring, allowed models, I/O contract, Docker constraints, or local-model wording, update this file, `README.md`, `Dockerfile`, runtime profiles, and official adapters before another submission attempt.
- If the Participant Guide contradicts the page, treat the newer official competition page plus Discord announcements as escalation points before changing runtime behavior.
