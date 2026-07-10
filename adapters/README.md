# Adapters

Responsavel por converter entradas e saidas entre o mundo externo e o `core`.

## Entradas previstas

- texto direto via CLI;
- stdin;
- JSON;
- JSONL;
- arquivo `.txt`;
- arquivo arbitrario com metadata;
- formato oficial do evaluator quando for revelado.

## Contrato inicial

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

## Saida inicial

```json
{
  "id": "same-task-id",
  "answer": "resposta final livre",
  "route": "deterministic|e2b|fireworks",
  "remote_tokens": {
    "prompt": 0,
    "completion": 0,
    "total": 0
  }
}
```

## Regra

Adapters podem mudar quando o kickoff revelar o formato real. O `core` deve mudar o minimo possivel.
