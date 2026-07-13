# Track 1 Token Router

General-purpose, token-efficient agent for AMD Developer Hackathon ACT II Track 1.

The runner handles factual Q&A, math reasoning, sentiment, summarization, NER, code debugging, logic puzzles and code generation. It targets the official accuracy gate first, then minimizes tokens routed through Fireworks.

## Championship Design

```text
task
-> strip official JSON envelope; retain task_id only in the engine
-> proof-carrying deterministic solver (release only a unique, recomputable result)
-> embedded FunctionGemma 270M Q8 assessment for unresolved tasks
-> independently verified FunctionGemma tool plan when structurally eligible
-> per-intent matrix selects embedded Gemma 4 E2B or Fireworks
-> Wilson 90% + Nash/minimax guard confirms or rejects the local decision
-> Kimi by default / MiniMax for logic, sentiment and summarization, only when authorized
-> strict output validation and allowed-model fallback
-> Answer Contract Engine normalization and validation
-> atomically rebuild [{task_id, answer}, ...]
-> final answer
```

`Dockerfile.championship` downloads hash-pinned artifacts only while building and embeds them in the image; the submitted container never downloads models during evaluation.

- Deterministic solvers must independently accept the original input or refuse it.
- Kimi and MiniMax are validation-selected preferences and are never called unless the harness includes them in `ALLOWED_MODELS`.
- Strict-format failures can retry another ranked allowed model; model unavailability is cached per batch.
- The Answer Contract Engine performs only unambiguous mechanical transformations before the official JSON serializer.
- The category-calibration ledger contains `6,845` unique observations: `4,462` historical rows plus `2,383/2,400` expansion rows with valid FunctionGemma assessments. All `2,400` E2B answers were processed by the production Answer Contract Engine and independently labeled; `824` were correct.
- The frozen per-category challenger nominated factual QA, NER and sentiment. One-shot sealed evaluation promoted only sentiment: `44/46` selected answers were correct (`95.65%` precision, `85.47%` Wilson lower bound). Factual QA and NER remained remote because selected support was insufficient.
- The promoted v2 policy replays at `88.41%` local precision and `8.82%` zero-Fireworks-token coverage across all `6,845` rows, versus `83.58%` and `7.74%` for the previous matrix.
- The proof engine recovered both known correct deterministic ordering answers while refusing all five incorrect deterministic candidates. Its independent 260-case gate still reports 180 releases, 100% precision and zero false positives.
- Sprint 71 trained a strong semantic-v3 full-SFT assessor, but its Q8 candidate missed the frozen intent non-inferiority margin by `0.034 pp` and was not promoted.
- Sprint 72 rejected cluster augmentation because it reduced sentiment calibration coverage and worsened Brier score; no clustering dependency enters Docker.
- Sprint 73 added a hash-pinned Wilson 90% and deterministic minimax-regret guard without expanding the proven v2 decision surface. The raw `0.70` alternative fell to `84.81%` protected precision and was rejected.
- Sprint 74 rejected one-call verify-or-repair after it used `8.52%` more Fireworks tokens in the paired arena; direct Fireworks remains the fallback.

The canonical specification is [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md).

## Competition Constraints

- input is adapted to the official task contract and final output is valid `/output/results.json`;
- exit code 0 on success;
- maximum runtime 10 minutes;
- container ready within 60 seconds and each task below 30 seconds;
- all natural-language responses in English;
- final environment 4 GB RAM and 2 vCPU;
- public Docker image with a `linux/amd64` manifest;
- compressed image below 10 GB;
- no hardcoded or cached answers;
- Fireworks calls only through `FIREWORKS_BASE_URL` and only to `ALLOWED_MODELS`;
- local model tokens count as zero Fireworks tokens.

## Status

`v3.12.3-proof-pull-retry` is the current recommended championship candidate. It runs proof-carrying solvers before model assessment, enforces an absolute 28-second Fireworks deadline, rejects non-standard or duplicate-key JSON, contains no factual-answer lookup table, and expands one mechanically proven inventory grammar. Release run `29247825641` passed clean public pull, exact published-image execution, `linux/amd64`, sub-10 GB, 4 GB, 2 vCPU, no-network, official-contract, cold-start and OCI-label gates. `v3.12.1-no-hardcoded-startup-sla` is the immediate rollback; `v3.7.3-public-sample` remains the scored rollback with 84.2% official accuracy and 4,198 Fireworks tokens.

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

The release CI completed `774` tests with three environment-dependent skips.

## Official Offline Contract

```bash
ROUTER_MODE=mock \
python3 -m router submit-track1 \
  --input fixtures/official/lablab_track1_tasks.json \
  --output reports/generated/official-smoke-results.json
```

## Evaluator Environment

The submitted container does **not** use or bundle a `.env` file. At evaluation time, the official harness injects the three required variables directly into the container:

```text
FIREWORKS_API_KEY=<harness-provided key>
FIREWORKS_BASE_URL=<harness-provided scored endpoint>
ALLOWED_MODELS=<comma-separated permitted model IDs>
```

No additional evaluator configuration is required. The runtime reads these variables through `RouterConfig.from_env()`, routes every remote request through `FIREWORKS_BASE_URL`, and only selects normalized IDs present in `ALLOWED_MODELS`. `FIREWORKS_MODEL` and `FIREWORKS_CHAMPION_MODEL` are optional preferences, never authorization overrides.

Files such as `.env.example` and `runtime-profiles/*.env.example` are development templates only. `.env`, `.env.*`, credentials, tests, reports and local model artifacts are excluded from the Docker build context.

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
| [Category calibration V2](./reports/public/e2b-category-calibration-v2.md) | 6,845-row regression, per-category calibration and sealed promotion |
| [Semantic-v3 Q8 decision](./reports/public/functiongemma-semantic-v3-q8-decision.md) | Full-SFT/Q8 parity evidence and rejected promotion |
| [Cluster augmentation decision](./reports/public/scale789-cluster-augmented-e2b.md) | Production-compatible cluster and regression comparison |
| [Wilson-Nash ladder](./reports/public/wilson-nash-risk-ladder-v1.md) | Confidence bounds, minimax regret and protected replay |
| [Verify-or-repair arena](./reports/public/fireworks-verify-repair-arena-v3.md) | One-call reviewer accuracy and token break-even decision |
| [Expansion adjudication](./reports/public/e2b-expansion-adjudication.md) | 2,400 post-contract labels and independent agreement evidence |
| [Expansion championship](./reports/public/e2b-expansion-championship-scorecard.md) | Previous versus promoted local precision, coverage and token avoidance |
| [Router ML v3 contract audit](./reports/public/router-ml-v3.md) | AMD neural sweeps, protected replay and rejected runtime promotion |
| [Fireworks Champion v3](./reports/public/fireworks-champion-v3.md) | 800-prompt paired arena and retain decision |
| [Raw-prompt ablation](./reports/public/raw-prompt-answer-contract-ablation.md) | Byte-identical Kimi answers with 51.9% fewer Fireworks tokens |
| [v3.12.1 exact-image smoke](./reports/public/v3.12.1-exact-image-smoke.md) | Public pull, constrained offline, E2B, hybrid and retired public-suite evidence |
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

`three_route` is the final embedded-model mode. `fireworks` is the compact remote-only fallback profile.

```text
ROUTER_MODE=fireworks
ROUTER_MODE=three_route
```

## Public Image

The final hybrid championship candidate is:

```text
ghcr.io/rvbernucci/track1-token-router:v3.12.3-proof-pull-retry
```

It embeds separate FunctionGemma 270M Q8 assessment and tool-planner models plus text-only Gemma 4 E2B, requires no startup downloads, and falls through only to evaluator-authorized Fireworks models. Release run `29247825641` built, publicly pulled and gated the exact image under 4 GB RAM, 2 vCPU and disabled networking. Registry audit confirms OCI digest `sha256:ec0d62c4c08489e8b8f06abf26087d1c1bfa43128d330b591f8588976b333c59`, platform digest `sha256:782f1266a5b1e74f5adca9d7ebef21f1bb576f0c5ab81990965660a08c089c5e`, source revision `76df56564f0a17e0db8b743ceaac441f573ca104`, 2,938,881,530 compressed bytes and a five-second cold-start smoke.

## Fireworks

```bash
set -a
. ./.env.fireworks.local
set +a

python3 scripts/fireworks_smoke.py \
  --model accounts/fireworks/models/minimax-m3 \
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

The release policy is accuracy-first: deterministic answers require a recomputable proof, E2B runs only inside its calibrated matrix cohort, and every refusal or local failure uses an allowed Fireworks model. See the [final scorecard](./reports/public/final-hybrid-scorecard.md), [Pareto calibration](./reports/public/final-pareto-calibration.md) and [E2B regression report](./reports/public/e2b-270m-matrix-regression.md).
