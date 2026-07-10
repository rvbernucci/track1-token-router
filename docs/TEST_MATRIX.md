# Test Matrix

This matrix maps critical project areas to automated tests and playground probes.

| Domain | Critical logic | Automated tests | Playground | Fixture/docs |
|---|---|---|---|---|
| contracts | `TaskEnvelope`, `AnswerResult`, assessment, feature-vector, decision, outcome and trace serialization | `tests/test_contracts.py`, `tests/test_assessment_contracts.py` | none | `schemas/*.schema.json`, `docs/ASSESSMENT_DECISION_CONTRACTS.md` |
| adapters | JSON, JSONL, official adapter templates, ACT II `/input/tasks.json` contract | `tests/test_io_and_cli.py`, `tests/test_official_adapters.py` | `playground/test_adapter_logic.py` | `fixtures/official/` |
| policies | policy normalization, route simulation, Pareto comparison, decision replay | `tests/test_policy_lab.py`, `tests/test_policy_optimizer_replay.py` | `playground/test_policy_logic.py` | `reports/OFFLINE_RC_REPORT.md` |
| fireworks_model_router | allowed model ranking, cheap/medium/strong task routing | `tests/test_fireworks_model_router.py`, `tests/test_fireworks_runner.py` | none | `docs/PARTICIPANT_GUIDE_TRACK1_MAP.md` |
| matrix_regression_selector | offline ridge regression fit, learned model selection, weights roundtrip, paid-result leaderboard | `tests/test_matrix_regression_selector.py`, `tests/test_fireworks_results_leaderboard.py` | none | `docs/MATRIX_REGRESSION_SELECTION.md`, `reports/generated/fireworks-results-leaderboard.md` |
| router schema | Target model IDs, runtime profiles and strict configuration boundaries | `tests/test_runtime_profiles.py`, `tests/test_config.py` | none | `docs/FUNCTIONGEMMA_ROUTER_SPEC.md` |
| three routes | FunctionGemma/E2B challenger, outcome prediction, minimax regret and fail-closed fallback | `tests/test_three_route_runner.py`, `tests/test_three_route_factory.py`, `tests/test_game_theory_selector.py` | none | `docs/ARCHITECTURE.md` |
| championship | Frozen evidence hashes, accuracy-first ablation, lineage bootstrap and score-shift stress | `tests/test_freeze_championship_evidence.py`, `tests/test_championship_ablation.py`, `tests/test_score_shift_stress.py` | none | `data/championship-ablation/`, `reports/public/championship-ablation.md` |
| container gate | Linux `amd64`, 4 GB, 2 vCPU, 10-minute timeout, image size and official output contract | `tests/test_docker_resource_gate.py`, CI and release workflows | none | `scripts/docker_resource_gate.sh`, `docker/README.md` |
| fake_provider | fake OpenAI-compatible server, chaos profiles | `tests/test_fake_provider.py`, `tests/test_bad_local_model_chaos.py` | none | `docs/CHAOS_LAB.md`, `fixtures/chaos/bad-local-model/` |
| evals | offline dataset, eval summary, policy comparison, semantic validation | `tests/test_eval_summary.py`, `tests/test_offline_dataset.py`, `tests/test_policy_lab.py`, `tests/test_semantic_validation.py` | none | `evals/offline/README.md`, `evals/semantic/` |
| deterministic_coverage | Track 1 solver/guardrail coverage, local validator pass rate, zero-token regression guard | `tests/test_track1_deterministic_coverage.py` | none | `evals/fireworks-pareto/*microbench.jsonl`, `reports/generated/track1-deterministic-coverage.md` |
| operational_envelope | latency percentiles, timeout probes, token exposure thresholds, batch stress | `tests/test_operational_envelope.py`, `tests/test_battle_drill.py`, `tests/test_batch_stress.py` | none | `reports/generated/latency-report.md`, `reports/generated/token-envelope.md`, `fixtures/stress/` |
| cli | ask, solve, run, eval, official submit-track1, controlled errors, submission rehearsal | `tests/test_io_and_cli.py`, `tests/test_official_adapters.py`, `tests/test_redaction_rehearsal.py` | none | `README.md`, `docs/SUBMISSION_REHEARSAL.md`, `docs/PARTICIPANT_GUIDE_TRACK1_MAP.md` |

## Coverage Rule

Every domain must have at least one automated test. Playground files are optional but useful for exploratory work.

## External Boundary

Real official scoring remains external to the repository. The public evidence pack reproduces internal model selection, while the release workflow proves the exact image contract and resource envelope before submission.
