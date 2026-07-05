# Slides Outline

## Slide 1 - Title

Track 1 Token Router: Local-first accuracy with selective remote audit.

## Slide 2 - Challenge

Track 1 rewards correct answers with minimal remote token usage. The core tension is accuracy versus cost.

## Slide 3 - Strategy

Do not route everything to the strongest model. Route only when risk signals justify the token spend.

## Slide 4 - Architecture

Guardrails and solvers first, then M1 local generation, M2A local verification, M2B local repair and Fireworks approve-or-replace audit.

## Slide 5 - Competition Mode

One integrated runner with budget policy, final validation, prompt packet estimation and trace logging.

## Slide 6 - Offline Readiness

Fuzz pack, battle drill, scoring simulator, Docker, CI, secret scan and runtime profile checks all run without credits.

## Slide 7 - AMD/Fireworks Activation

Runtime profiles are ready for AMD/DigitalOcean MI300X with vLLM or SGLang, Gemma local models and Fireworks serverless audit.

## Slide 8 - Demo

Show CLI `ask`, JSON output, route trace, zero remote tokens for solver path and battle drill readiness.

## Slide 9 - Why It Can Win

Mechanical tasks avoid models, easy tasks stay local, risky tasks escalate with compact remote packets.

## Slide 10 - Remaining Kickoff Work

Plug in real AMD endpoint, calibrate Fireworks model, adapt official input format and run final benchmark.
