# Speaker Notes

## Slide 1 - Title

Track 1 Token Router: General-purpose accuracy with token-efficient Fireworks routing.

## Slide 2 - Challenge

Track 1 rewards correct answers with minimal remote token usage. The core tension is accuracy versus cost.

## Slide 3 - Strategy

Do not route everything to the strongest model. Route only when risk signals justify the token spend.

## Slide 4 - Architecture

Fail-closed solvers answer only provable templates. FunctionGemma assesses the remaining prompts, a calibrated matrix and Wilson-Nash guard select safe E2B tasks, and all uncertainty falls through to an authorized Firewo...

## Slide 5 - Competition Mode

One integrated runner with raw-prompt inference, Answer Contract validation, deterministic JSON reconstruction and trace logging.

## Slide 6 - Offline Readiness

Fuzz pack, battle drill, scoring simulator, Docker, CI, secret scan and runtime profile checks all run without credits.

## Slide 7 - AMD/Fireworks Activation

The AMD pod trained FunctionGemma and benchmarked E2B. The final image embeds both quantized local models and exact-image testing proves zero-token local inference under evaluator limits.

## Slide 8 - Demo

Show CLI `ask`, JSON output, route trace, model selection and battle drill readiness.

## Slide 9 - Why It Can Win

The router avoids unnecessary token spend, keeps prompts compact and escalates only when the expected accuracy gain justifies the Fireworks cost.

## Slide 10 - Championship Decision

Frozen gates promoted the Wilson-Nash guard while rejecting semantic-v3 Q8, cluster augmentation and verify-or-repair. The public v3.7 image is the evidence-backed championship release.
