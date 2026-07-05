# Offline Evaluation Arena

Generated deterministic dataset for offline calibration.

## Shape

- total tasks: 160
- categories: facil, media, dificil, formato, matematica, instrucao, adversarial, conhecimento_instavel
- tasks per category: 20

## Regenerate

```bash
python3 scripts/generate_offline_eval.py
```

## Validate

```bash
python3 scripts/generate_offline_eval.py --check
python3 -m router eval --jsonl evals/offline/tasks.jsonl --expected evals/offline/expected.jsonl --report reports/generated/offline-report.md
```

## Metadata

Each task includes:

- `metadata.category`
- `metadata.difficulty`
- `metadata.expected_route`
- `metadata.risk`
