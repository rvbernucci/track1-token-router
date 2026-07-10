# Championship Architecture

Updated: 2026-07-10

## Promoted Runtime

The submitted runtime is the smallest architecture that survived the frozen accuracy-first ablation:

```text
official task
-> registered deterministic solver (accept or refuse)
-> validation-selected Kimi K2.7 Code, only when present in ALLOWED_MODELS
-> strict output validation and safe formatting repair
-> next allowed model on fast unavailability or invalid strict output
-> /output/results.json
```

The goal is to pass the Track 1 accuracy gate first and then minimize tokens sent through `FIREWORKS_BASE_URL`. The runtime never calls a model outside `ALLOWED_MODELS`, never downloads at startup and never embeds answers.

## Selection Evidence

All routes and model choices were frozen on validation. The locked test was opened once as a pass/fail promotion gate.

| Variant | Validation accuracy | Locked-test accuracy | Locked-test Fireworks tokens |
| --- | ---: | ---: | ---: |
| deterministic then Kimi | 58.45% | 59.58% | 73,870 |
| Kimi only | 58.45% | 59.58% | 73,870 |
| matrix plus Pareto/Nash | 57.39% | 57.84% | 78,853 |
| validation intent candidate | 59.15% | 56.10% | 81,474 |
| rejected E2B challenger | 58.45% | 54.70% | 57,103 |
| Minimax only | 56.69% | 50.52% | 101,447 |

Accuracy is conservative: judge disagreement counts as not correct. Kimi's binary locked-test accuracy is 75.0%. The full report and lineage bootstrap are in `reports/public/championship-ablation.md`.

## Deterministic Route

Solvers receive the untouched task and must prove an exact registered contract. They cannot use a FunctionGemma label as authorization. Unknown, ambiguous or unsupported inputs refuse and continue to Fireworks. The hardened registry accepted `0/571` broad frozen tasks, demonstrating fail-closed behavior; it remains useful for exact unseen arithmetic, transforms and structured templates covered by adversarial tests.

## Fireworks Route

`FIREWORKS_CHAMPION_MODEL` is a preference, not an authorization. Kimi is used first only when its normalized model ID appears in the harness-provided `ALLOWED_MODELS`. Otherwise the runtime falls back to the allowed-model Pareto/Nash ordering. A 404 is cached for the batch. A timeout does not cascade across models, preserving the deadline. Strictly invalid JSON, number, yes/no or code output can fall through to the next ranked allowed model.

Dynamic completion ceilings reduce scored tokens while preserving output headroom:

- yes/no: 8;
- simple numeric: 16-48;
- classification and short formats: 48-64;
- extraction and summaries: up to 160;
- JSON: up to 224;
- code: up to 384, bounded by the global evaluator setting.

## Rejected Gemma Challenger

The research architecture was implemented end to end:

```text
FunctionGemma 270M assessment
-> five scores plus intent
-> outcome regression and minimax regret
-> deterministic | Gemma 4 E2B | Fireworks
```

FunctionGemma was fine-tuned on the AMD pod and quantized to Q8. Gemma 4 E2B ran text-only on CPU. Their summed process high-water RSS was 2.649 GiB, leaving 1,383 MiB below 4 GiB. However, the 2,000-task locked experiment found no safe E2B region: selected accuracy was 51.14% with a 40.87% Wilson lower bound against the 60% gate. More output tokens produced limited recoveries and did not solve the quality problem.

Because E2B failed the accuracy gate, FunctionGemma could no longer create a measured token-saving route. Bundling either model would add startup, memory and image risk without improving the promoted policy. Both remain reproducible research artifacts and optional runtime modes, but are absent from the final image.

## Failure Policy

| Failure | Action |
| --- | --- |
| Deterministic solver refusal | Fireworks |
| Preferred model absent from `ALLOWED_MODELS` | Select another allowed model |
| Fast 404 or inaccessible model | Cache and try the next allowed model |
| Timeout | Stop model cascade and preserve batch deadline |
| Invalid strict output | Try the next ranked allowed model when time remains |
| Deadline reserve reached | Emit a controlled valid result and preserve `results.json` |

## Delivery Gates

- public Linux `amd64` manifest;
- compressed image below 10 GB;
- exact run under 4 GB RAM and 2 vCPU;
- complete run below 10 minutes;
- valid `/output/results.json` and exit code 0;
- no credentials, hardcoded answers or startup downloads;
- only `FIREWORKS_BASE_URL` and `ALLOWED_MODELS` for scored inference.

## Non-Goals

- No LLM judge in the runtime answer path.
- No embeddings, RAG or multimodality.
- No post-hoc tuning on the locked test.
- No local model retained merely for partner branding.
- No API-dollar optimization in place of the official token objective.
