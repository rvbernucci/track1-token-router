# Sprints 45-49 Completion Audit

Audit date: 2026-07-10

This report maps each sprint's promotion gate to current, reproducible evidence. A checked sprint means its experiment and decision are complete; it does not imply that every challenger was promoted.

## Sprint 45 - Assessment And Decision Contracts

- Contracts: `schemas/task-assessment-v1.schema.json`, `schemas/feature-vector-v1.schema.json`, `schemas/engine-outcome-v1.schema.json` and `schemas/routing-trace-v1.schema.json`.
- Runtime invariant: model output cannot directly select an engine; invalid assessments fail closed to Fireworks.
- Focused gate: `python3 -m unittest tests.test_assessment_contracts`.
- Completion record: `sprints/45-three-route-architecture-migration/README.md`.

Result: promoted.

## Sprint 46 - FunctionGemma Assessment Training

- Reproducible experiment configuration: `configs/functiongemma-sprint46.json`.
- Champion provenance: `configs/functiongemma-scale789-q8-manifest.json`.
- Runtime protocol: `configs/functiongemma-scale789-q8-runtime.json`.
- Checked-in calibration: `configs/functiongemma-scale789-q8-calibration.json`.
- Public pilot evidence: `reports/public/functiongemma-dataset-pilot.md`.
- AMD evidence: full SFT and LoRA comparisons were run on ROCm; the scale-789 LoRA R16 champion was merged and exported as Q8_0.
- Quantization gate: Q8 and BF16 produced identical parsed assessments on 93/93 validation tasks.

Result: FunctionGemma scale-789 Q8 promoted as the assessment challenger.

## Sprint 47 - Engine Outcome Matrix

- Matrix schema: `schemas/engine-outcome-matrix-row-v1.schema.json`.
- Cross-model judgment policies: `configs/engine-matrix-judge-policy.json` and `configs/e2b-regression-judge-policy.json`.
- Token-ladder evidence: `reports/public/e2b-token-ladder.md`.
- Frozen 2,000-task corpus: `data/e2b-regression-2000/manifest.json`.
- Local resource evidence: FunctionGemma plus E2B measured 2.649 GiB combined VmHWM, inside the 4 GiB envelope.
- Outcome evidence: the initial E2B matrix did not support an accuracy-safe intent allowlist.

Result: matrix and resource work completed; E2B retained as a challenger and disabled by default.

## Sprint 48 - Regression And Game-Theory Decision Engine

- Fitted outcomes: `configs/engine-outcome-models-v1.json`.
- E2B promotion policy: `configs/e2b-route-policy-v1.json`, `default_enabled=false`.
- Fireworks intent policy: `configs/fireworks-intent-policy-v1.json`, `default_enabled=false`.
- Locked E2B gate: 88/286 tasks selected, 51.14% conservative accuracy and 40.87% Wilson lower bound against a 60% gate.
- Fireworks exact-runtime evidence: Kimi and Minimax completed the frozen 571-task comparison; the validation-selected per-intent policy failed the locked-test gate.
- Robustness gate: every one of 17,070 five-score perturbations preserved the safe Fireworks route in `reports/public/score-shift-stress.md`.

Result: decision engine completed; both E2B and per-intent candidates rejected, with fail-safe policy hashes pinned.

## Sprint 49 - Championship Calibration

- Frozen evidence manifest: `data/championship-ablation/manifest.json`.
- Identical-task ablation: `reports/public/championship-ablation.md`.
- Promoted runtime: deterministic solver acceptance followed by Kimi when allowed, then strict allowed-model fallback.
- Locked test: 171/287 conservative correctness, 75.0% binary accuracy and 73,870 Fireworks tokens.
- Public image: `ghcr.io/rvbernucci/track1-token-router:v1.0.0-championship`.
- Image revision: `8cbe0c58333486278f467d27ea9f27093eb68e99`.
- Platform manifest: `sha256:b88778e89291dc7a21f638a4347e0c4ba0ef8d156a43a45ae248215d40f4bb5e`, Linux `amd64`, 45,522,326 registry-compressed bytes.
- Exact public-image run: GitHub Actions `29108270058` anonymously pulled the tag and passed 4 GiB RAM, 2 CPU, no-network, 600-second timeout and official result-shape gates.
- Observed public-image smoke: 1 second outer runtime, 10 ms process time and 28.348 MiB process peak RSS.
- Final CI: GitHub Actions `29108264888` passed Python 3.10, Python 3.12 and Docker jobs.

Result: promoted and released.

## Final Invariants

- No unchecked item remains in the five sprint checklists.
- FunctionGemma and E2B evidence is preserved, but their weights are not bundled because E2B failed the frozen accuracy gate.
- The final Docker image makes no startup downloads and contains no embedded provider credentials.
- Fireworks requests use `FIREWORKS_BASE_URL` and cannot select a model outside `ALLOWED_MODELS`.
- The exact public image is pullable, under 10 GB, Linux `amd64`, traceable to its source revision and compliant with the official output contract.
- `scripts/offline_release_check.sh` is the aggregate local/CI gate; `scripts/competition_submission_audit.py` is the evaluator-facing public-image gate.
