# Track 1 Token Router

General-purpose, token-efficient agent for AMD Developer Hackathon ACT II Track 1.

The runner handles factual Q&A, math reasoning, sentiment, summarization, NER, code debugging, logic puzzles and code generation. It targets the official accuracy gate first, then minimizes tokens routed through Fireworks.

## Championship Design

```text
task
-> strip official JSON envelope; retain task_id only in the engine
-> proof-carrying deterministic solver (release only a unique, recomputable result)
-> Kimi K2.7 Code when present in ALLOWED_MODELS
-> strict output validation and allowed-model fallback
-> Answer Contract Engine normalization and validation
-> atomically rebuild [{task_id, answer}, ...]
-> final answer
```

The local challenger inserts `FunctionGemma five-parameter assessment -> intent-specific matrix regression -> E2B or Fireworks` after envelope removal. Its runtime remains optional because the 2.59 GB LiteRT artifact must be bundled at image-build time; the submitted image never downloads models during evaluation.

- Deterministic solvers must independently accept the original input or refuse it.
- Kimi is a validation-selected preference and is never called unless the harness includes it in `ALLOWED_MODELS`.
- Strict-format failures can retry another ranked allowed model; model unavailability is cached per batch.
- The Answer Contract Engine performs only unambiguous mechanical transformations before the official JSON serializer.
- FunctionGemma 270M and Gemma 4 E2B were evaluated on 2,000 post-contract answers. E2B produced 828 correct answers; 823 had valid 270M parameters. The intent-specific regression selected 252 of 1,991 evaluable tasks at 84.52% out-of-fold precision and 12.66% coverage.
- The proof engine recovered both known correct deterministic ordering answers while refusing all five incorrect deterministic candidates. Its independent 260-case gate still reports 180 releases, 100% precision and zero false positives.

The canonical specification is [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md).

## Competition Constraints

- input is adapted to the official task contract and final output is valid `/output/results.json`;
- exit code 0 on success;
- maximum runtime 10 minutes;
- final environment 4 GB RAM and 2 vCPU;
- public Docker image with a `linux/amd64` manifest;
- compressed image below 10 GB;
- no hardcoded or cached answers;
- Fireworks calls only through `FIREWORKS_BASE_URL` and only to `ALLOWED_MODELS`;
- local model tokens count as zero Fireworks tokens.

## Status

The public championship image passed the exact `linux/amd64`, 4 GB, 2 vCPU, no-network and official-contract gates. The proof-carrying deterministic route is promoted. The calibrated E2B artifact is reproducible and documented, but is not silently enabled in an image that does not contain its pinned model artifact.

## Quickstart

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python -m router ask "What is 2+2?"
```

Run the current offline checks:

```bash
python3 -m unittest discover -s tests
python3 scripts/track1_deterministic_coverage.py --check
python3 scripts/competition_submission_audit.py --skip-network
scripts/offline_release_check.sh
python3 scripts/secret_scan.py
git diff --check
```

## Official Offline Contract

```bash
ROUTER_MODE=mock \
python3 -m router submit-track1 \
  --input fixtures/official/lablab_track1_tasks.json \
  --output reports/generated/official-smoke-results.json
```

## Documentation

| Document | Purpose |
|---|---|
| [Architecture](./docs/ARCHITECTURE.md) | Canonical three-route design and fallback policy |
| [Answer Contract Engine](./docs/ANSWER_CONTRACT_ENGINE.md) | Safe response normalization before official JSON serialization |
| [Assessment contracts](./docs/ASSESSMENT_DECISION_CONTRACTS.md) | Taxonomy, score anchors, feature vector, outcomes and fail-closed trace |
| [FunctionGemma assessment spec](./docs/FUNCTIONGEMMA_ROUTER_SPEC.md) | Intent, five score rubrics and evaluation contract |
| [AMD training tutorial](./docs/FUNCTIONGEMMA_270M_AMD_TRAINING_TUTORIAL.md) | Full SFT and LoRA workflow on ROCm |
| [Gemma E2B token ladder](./docs/E2B_TOKEN_LADDER.md) | Adaptive 96/192/384 experiment, quantization and CPU runtime audit |
| [Public E2B evidence](./reports/public/e2b-token-ladder.md) | Aggregate recovery, feature and latency results |
| [E2B 270M matrix regression](./reports/public/e2b-270m-matrix-regression.md) | Post-contract correctness, model comparison and operating frontier |
| [Raw-prompt ablation](./reports/public/raw-prompt-answer-contract-ablation.md) | Byte-identical Kimi answers with 51.9% fewer Fireworks tokens |
| [Sprints 45-49 completion audit](./reports/public/sprints-45-49-completion-audit.md) | Requirement-to-evidence map and final release proof |
| [E2B runtime](./docs/GEMMA_E2B_TEXT_ONLY_RUNTIME.md) | Text-only LiteRT-LM packaging and 4 GB gates |
| [Deterministic solvers](./docs/DETERMINISTIC_SOLVERS.md) | Mechanical registry and proof rules |
| [Fireworks calibration](./docs/FIREWORKS_TRACK1_ALLOWED_CALIBRATION.md) | Allowed-model microbench workflow |
| [Pareto routing](./docs/PARETO_MODEL_ROUTING.md) | Cheapest-sufficient remote selection |
| [Game theory](./docs/GAME_THEORY_MODEL_SELECTION.md) | Payoff and equilibrium model selection |
| [Final environment](./docs/TRACK1_FINAL_ENVIRONMENT_STRATEGY.md) | Official resource and submission constraints |
| [Testing culture](./docs/TESTING_CULTURE.md) | Promotion and regression discipline |
| [Sprints](./sprints/README.md) | Active implementation plan |

## Repository Map

| Path | Role |
|---|---|
| `router/` | Runtime, adapters, solvers, Fireworks and orchestration |
| `tests/` | Unit and integration regression suite |
| `evals/` | Golden, adversarial, semantic and Fireworks calibration sets |
| `scripts/` | Training support, audits, benchmarks and release checks |
| `docs/` | Current technical documentation |
| `sprints/` | Completed history and active migration work |
| `submission/` | Pitch, demo and delivery assets |

## Runtime Modes

`fireworks` is the zero-download Docker mode. `three_route` is available when the pinned FunctionGemma and E2B endpoints are supplied.

```text
ROUTER_MODE=fireworks
ROUTER_MODE=three_route
```

## Public Image

The audited championship image is:

```text
ghcr.io/rvbernucci/track1-token-router:v2.1.0-proof-router
```

The release workflow verifies the public `linux/amd64` manifest, immutable revision label, anonymous pull and exact-image resource gate.

## Fireworks

```bash
set -a
. ./.env.fireworks.local
set +a

python3 scripts/fireworks_smoke.py \
  --model accounts/fireworks/models/gemma-4-31b-it \
  --json
```

Never commit real credentials. The harness-provided `ALLOWED_MODELS` always overrides local preference during scoring.

## AMD Pod

```bash
git clone https://github.com/rvbernucci/track1-token-router.git
cd track1-token-router
/opt/venv/bin/python scripts/amd_pod_doctor.py --json
```

Use the preinstalled ROCm/PyTorch stack. Training instructions are in the AMD FunctionGemma tutorial linked above.

## Promotion Rule

The release policy is accuracy-first: deterministic answers require a recomputable proof; unsupported tasks use an allowed Fireworks model. The E2B matrix is an optional token-saving challenger whose measured operating point is documented rather than overstated. See [the public ablation](./reports/public/championship-ablation.md) and [the E2B regression report](./reports/public/e2b-270m-matrix-regression.md).
