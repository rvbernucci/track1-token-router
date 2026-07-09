# Official Competition Sync

Last checked: 2026-07-09

Source of truth: <https://lablab.ai/ai-hackathons/amd-developer-hackathon-act-ii>

## Track Choice

We are targeting Track 1: Hybrid Token-Efficient Routing Agent.

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

## Submission Requirements

- All submissions must be containerized.
- The GitHub repository must be public.
- The repository must include setup and usage instructions.
- The application must be runnable using the provided instructions.
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
- `ROUTER_MODE=hybrid` is the championship profile when a local OpenAI-compatible model endpoint is available.
- `ROUTER_MODE=fireworks` remains the safest fallback when no local endpoint is available.
- `scripts/amd_pod_doctor.py` verifies the AMD pod before model downloads.
- `scripts/bootstrap_amd_pod.sh` validates clone-to-smoke bootstrap on the AMD notebook.
- `FIREWORKS_MATRIX_WEIGHTS` can enable microbench-calibrated model selection for Fireworks fallback.

## Watch Items

- If lablab.ai changes Track 1 scoring, allowed models, I/O contract, Docker constraints, or local-model wording, update this file, `README.md`, `Dockerfile`, runtime profiles, and official adapters before another submission attempt.
- If the Participant Guide contradicts the page, treat the newer official competition page plus Discord announcements as escalation points before changing runtime behavior.
