# Test Matrix

This matrix maps critical project areas to automated tests and playground probes.

| Domain | Critical logic | Automated tests | Playground | Fixture/docs |
|---|---|---|---|---|
| contracts | `TaskEnvelope`, `AnswerResult`, token usage serialization | `tests/test_contracts.py` | none | none |
| adapters | JSON, JSONL, official adapter templates | `tests/test_io_and_cli.py`, `tests/test_official_adapters.py` | `playground/test_adapter_logic.py` | `fixtures/official/` |
| policies | policy normalization, route simulation, Pareto comparison | `tests/test_policy_lab.py` | `playground/test_policy_logic.py` | `reports/OFFLINE_RC_REPORT.md` |
| prompts | M1/M2A/M2B/Fireworks prompt packet shape | `tests/test_local_m1.py`, `tests/test_local_cascade.py`, `tests/test_hybrid_cascade.py` | `playground/test_prompt_packets.py` | `docs/TESTING_CULTURE.md` |
| cascade | M1, M2A, M2B, hybrid audit routing | `tests/test_local_cascade.py`, `tests/test_hybrid_cascade.py` | none | `SUBMISSION.md` |
| fake_provider | fake OpenAI-compatible server, chaos profiles | `tests/test_fake_provider.py` | none | `docs/CHAOS_LAB.md` |
| evals | offline dataset, eval summary, policy comparison | `tests/test_eval_summary.py`, `tests/test_offline_dataset.py`, `tests/test_policy_lab.py` | none | `evals/offline/README.md` |
| operational_envelope | latency percentiles, timeout probes, token exposure thresholds | `tests/test_operational_envelope.py`, `tests/test_battle_drill.py` | none | `reports/generated/latency-report.md`, `reports/generated/token-envelope.md` |
| cli | ask, solve, run, eval, controlled errors | `tests/test_io_and_cli.py` | none | `README.md` |

## Coverage Rule

Every domain must have at least one automated test. Playground files are optional but useful for exploratory work.

## Current Gaps

- No real AMD runtime tests because credits are not available.
- No real Fireworks audit tests because credits are not available.
- No official evaluator adapter because the kickoff format is not public yet; simulated adapter drills exist under `fixtures/adapter-drill/`.
