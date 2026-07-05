# Golden Eval Set

Dataset inicial para calibrar o roteador antes do kickoff.

Ele nao pretende representar o scoring oficial. Serve para medir regressao local, distribuicao de rotas, tokens remotos e comportamento em tarefas faceis, medias, dificeis e adversariais.

## Arquivos

- `tasks.jsonl`: tarefas de entrada.
- `expected.jsonl`: respostas esperadas para exact match simples.

## Uso

```bash
python3 -m router eval \
  --jsonl evals/golden/tasks.jsonl \
  --expected evals/golden/expected.jsonl \
  --out reports/generated/golden-output.jsonl \
  --report reports/generated/golden-report.md
```

