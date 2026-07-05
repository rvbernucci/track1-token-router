# Kickoff Adapter Drill

## Goal

Be able to adapt to an official evaluator contract in less than 30 minutes without destabilizing the router core.

## Drill Command

```bash
python3 scripts/adapter_drill.py --check --report reports/generated/adapter-drill-report.md
python3 -m unittest tests.test_official_adapters
```

## Simulated Formats

- `scoring_text_batch`: a plain text batch with explicit task headers and tab-separated answers.
- `scoring_json_envelope`: a JSON object that carries scoring metadata and task prompts.
- `scoring_file_bundle`: a JSON object with inline attachment content and a plain-text output contract.

## 30-Minute Kickoff Procedure

1. Copy the official sample input into `fixtures/adapter-drill/official_sample.*`.
2. Decide whether an existing adapter can parse it with a small modification.
3. If not, create a new adapter under `router/adapters/official/`.
4. Register it in `router/adapters/official/__init__.py`.
5. Add one test that proves parse ids, input text, files and output formatting.
6. Run `python3 scripts/adapter_drill.py --check`.
7. Run `scripts/offline_release_check.sh` before claiming readiness.

## Guardrails

- Do not edit `router/core/*` for a pure input/output format surprise.
- Do not print traces, prompts, JSON diagnostics or provider metadata to stdout on evaluator paths.
- Do not add dependencies during kickoff unless the official contract absolutely requires them.
- Do not rely on private local files, caches or non-reproducible state.
- Keep the first patch boring: fixture, adapter, test, report.

## Success Criteria

- Official sample parses into `TaskEnvelope`.
- Formatted answer satisfies the official output contract.
- Existing CLI, fuzz and battle drills still pass.
- The change touches adapter and fixture layers only unless the core contract truly needs expansion.
