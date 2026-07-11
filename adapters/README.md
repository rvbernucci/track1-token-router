# Adapters

Responsible for converting inputs and outputs between the external world and the `core`.

## Expected inputs

- direct text via CLI;
- stdin;
- JSON;
- JSONL;
- `.txt` file;
- arbitrary file with metadata;
- official evaluator format when revealed.

## Initial contract

```json
{
  "id": "optional-task-id",
  "input_text": "texto principal, se houver",
  "files": [
    {
      "name": "file.ext",
      "path": "/tmp/file.ext",
      "mime_type": "text/plain"
    }
  ],
  "metadata": {}
}
```

## Initial output

```json
{
  "id": "same-task-id",
  "answer": "free-form final answer",
  "route": "deterministic|e2b|fireworks",
  "remote_tokens": {
    "prompt": 0,
    "completion": 0,
    "total": 0
  }
}
```

## Rule

Adapters may change when the kickoff reveals the actual format. The `core` should change as little as possible.
