# Official Adapter Templates

This folder is the kickoff buffer.

The core runner should keep speaking only:

- `TaskEnvelope`
- `AnswerResult`

Official input/output formats should be translated here.

## Existing templates

- `plain_text`: one raw text task.
- `json_task`: one JSON task object.
- `jsonl_batch`: many JSON task objects, one per line.
- `file_payload`: one JSON task object with file metadata.

## Add a new adapter in 30 minutes

1. Create `router/adapters/official/<format_name>.py`.
2. Implement `parse(raw: str) -> list[TaskEnvelope]`.
3. Implement `format(results: list[AnswerResult]) -> str`.
4. Register it in `router/adapters/official/__init__.py`.
5. Add a fixture under `fixtures/official/`.
6. Add a round-trip test in `tests/test_official_adapters.py`.
7. Do not edit `router/core/*` unless the official contract truly changes the task model.
