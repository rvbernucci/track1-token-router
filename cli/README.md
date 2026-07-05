# CLI

Responsavel pela interface de linha de comando.

## Comandos alvo

```bash
router ask "What is 2+2?"
router ask --file ./task.txt
router solve --json < task.json
router run --jsonl ./tasks.jsonl --out ./runs/output.jsonl
router eval --jsonl ./tasks.jsonl --expected ./expected.jsonl
```

## Regras

- O CLI deve ser fino: parseia argumentos e chama o `core`.
- O stdout deve ficar limpo.
- Logs humanos vao para stderr.
- Logs estruturados vao para `logs/` ou caminho definido por flag/env var.

## Por que CLI-first

Track 1 parece ser benchmark/evaluator, nao produto visual. CLI facilita:

- containerizacao;
- reproducibilidade;
- execucao por JSONL;
- integracao com avaliador;
- testes automatizados;
- medicao de tokens e rotas.

