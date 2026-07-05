# Logs

Pasta para logs locais de execucao.

## Objetivo

Guardar rastros suficientes para aprender a politica de roteamento sem contaminar stdout.

## Formato recomendado

JSONL, uma linha por task:

```json
{
  "task_id": "abc",
  "route": "m1_approved",
  "model_1_ms": 120,
  "model_2a_ms": 450,
  "model_2b_ms": 0,
  "remote_ms": 0,
  "remote_prompt_tokens": 0,
  "remote_completion_tokens": 0,
  "remote_total_tokens": 0,
  "final_answer": "4"
}
```

## Relatorio local

```bash
python3 scripts/analyze_traces.py --logs "logs/*.jsonl" --report reports/generated/trace-summary.md
```

O relatorio agrega rotas, tokens remotos, latencia por etapa, erros e falhas de parsing.

## Nao colocar aqui

- API keys.
- secrets.
- arquivos grandes.
- pesos de modelo.
- dados que o evaluator nao permite persistir.
