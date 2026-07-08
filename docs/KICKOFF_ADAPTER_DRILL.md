# Kickoff Adapter Drill

## Goal

Be able to adapt to an official evaluator contract in less than 30 minutes without destabilizing the router core.

## Drill Command

```bash
python3 scripts/adapter_drill.py --check --report reports/generated/adapter-drill-report.md
python3 -m unittest tests.test_official_adapters
```

## Simulated Formats

- `lablab_track1`: official ACT II Track 1 `/input/tasks.json` to `/output/results.json`.
- `scoring_text_batch`: a plain text batch with explicit task headers and tab-separated answers.
- `scoring_json_envelope`: a JSON object that carries scoring metadata and task prompts.
- `scoring_file_bundle`: a JSON object with inline attachment content and a plain-text output contract.

## 30-Minute Kickoff Procedure

1. Start from the confirmed `lablab_track1` adapter.
2. If launch-day input differs, copy the official sample input into `fixtures/adapter-drill/official_sample.*`.
3. Decide whether `lablab_track1` can parse it with a small modification.
4. If not, create a new adapter under `router/adapters/official/`.
5. Register it in `router/adapters/official/__init__.py`.
6. Add one test that proves parse ids, input text, files and output formatting.
7. Run `python3 scripts/adapter_drill.py --check`.
8. Run `scripts/offline_release_check.sh` before claiming readiness.

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
