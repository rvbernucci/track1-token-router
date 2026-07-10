# Slides Outline

## Slide 1 - Title

Track 1 Token Router: General-purpose accuracy with token-efficient Fireworks routing.

## Slide 2 - Challenge

Track 1 rewards correct answers with minimal remote token usage. The core tension is accuracy versus cost.

## Slide 3 - Strategy

Do not route everything to the strongest model. Route only when risk signals justify the token spend.

## Slide 4 - Architecture

Fail-closed solvers answer only provable templates. All other tasks use validation-selected Kimi when authorized, then strict output validation and allowed-model fallback.

## Slide 5 - Competition Mode

One integrated runner with budget policy, final validation, prompt packet estimation and trace logging.

## Slide 6 - Offline Readiness

Fuzz pack, battle drill, scoring simulator, Docker, CI, secret scan and runtime profile checks all run without credits.

## Slide 7 - AMD/Fireworks Activation

The AMD pod trained FunctionGemma and benchmarked E2B. Memory passed, accuracy did not, so the final image intentionally excludes both local models.

## Slide 8 - Demo

Show CLI `ask`, JSON output, route trace, model selection and battle drill readiness.

## Slide 9 - Why It Can Win

The router avoids unnecessary token spend, keeps prompts compact and escalates only when the expected accuracy gain justifies the Fireworks cost.

## Slide 10 - Championship Decision

The frozen ablation selected deterministic-then-Kimi: 75% binary locked-test accuracy, 73,870 tokens, and no post-test tuning.
