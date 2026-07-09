# Speaker Notes

## Slide 1 - Title

Track 1 Token Router: General-purpose accuracy with token-efficient Fireworks routing.

## Slide 2 - Challenge

Track 1 rewards correct answers with minimal remote token usage. The core tension is accuracy versus cost.

## Slide 3 - Strategy

Do not route everything to the strongest model. Route only when risk signals justify the token spend.

## Slide 4 - Architecture

Mechanical validators protect schema and high-confidence cases, then the router selects the cheapest sufficient Fireworks/Gemma-capable path for each task.

## Slide 5 - Competition Mode

One integrated runner with budget policy, final validation, prompt packet estimation and trace logging.

## Slide 6 - Offline Readiness

Fuzz pack, battle drill, scoring simulator, Docker, CI, secret scan and runtime profile checks all run without credits.

## Slide 7 - AMD/Fireworks Activation

Runtime profiles are ready for AMD/Gemma development and Fireworks calibration, while the submitted Docker image stays compatible with the official CPU/RAM grading envelope.

## Slide 8 - Demo

Show CLI `ask`, JSON output, route trace, model selection and battle drill readiness.

## Slide 9 - Why It Can Win

The router avoids unnecessary token spend, keeps prompts compact and escalates only when the expected accuracy gain justifies the Fireworks cost.

## Slide 10 - Remaining Kickoff Work

Plug in real AMD endpoint, calibrate Fireworks model, adapt official input format and run final benchmark.
