# Runbook Native.Builder

## Objective

Use Native.Builder/NativelyAI as an auxiliary tool for demo, documentation, or presentation, not as a Track 1 competitive runtime.

## Correct Role

- Create a visual demo of the router flow.
- Generate navigable documentation for judges.
- Help with pitch/video.
- Do not replace CLI, eval harness, or scoring path.

## Safe Inputs

- Public description of the architecture.
- Screenshots without secrets.
- Reports generated without sensitive prompts.
- Mermaid or Markdown diagrams.

## Prohibited Inputs

- API keys.
- Private VM IP.
- Logs with sensitive prompts.
- Official evaluation data if confidentiality rules apply.

## Suggested Flow

1. Export `SUBMISSION.md`, `docs/DETERMINISTIC_SOLVERS.md` and the battle drill report.
2. Create an auxiliary demo explaining:
   - FunctionGemma assessment;
   - regression and minimax decision engine;
   - deterministic solver route;
   - Gemma 4 E2B text-only route;
   - Fireworks Pareto fallback.
3. Use the demo only as presentation material.
4. Keep the actual execution on the CLI.

## Positioning Health Check

If a change in Native.Builder is required for the technical score, we are on the wrong track.

The competitive core must remain reproducible by:

```bash
scripts/offline_release_check.sh
```
