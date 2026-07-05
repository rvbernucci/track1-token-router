# Sprint 34 - Semantic Validation Harness

## Tipo

Nao depende de credito.

## Objetivo

Criar um harness offline de validacao semantica para respostas livres e parcialmente abertas, sem depender de LLM judge pago.

## Por que importa

Exact match e excelente para regressao, mas fraco para perguntas abertas. Se o evaluator oficial trouxer respostas livres, precisamos medir "aceitavel", "parcial", "fora do formato" e "perigoso" de forma mais rica.

## Tese

Nao precisamos de um judge perfeito sem credito. Precisamos de um judge deterministico que exponha erros grosseiros e classes de risco antes de gastar tokens reais.

## Entregaveis

- `evals/semantic/`.
- `evals/semantic/tasks.jsonl`.
- `evals/semantic/rubrics.jsonl`.
- `router/evals/semantic_judge.py`.
- `scripts/run_semantic_eval.py`.
- `reports/generated/semantic-eval.md`.
- Testes para rubricas, formatos e classes de erro.

## Checklist

- [ ] Definir schema de rubrica offline.
- [ ] Criar classes: `acceptable`, `partial`, `format_fail`, `unsafe`, `hallucinated`, `too_verbose`.
- [ ] Criar tarefas abertas de explicacao curta.
- [ ] Criar tarefas de resumo.
- [ ] Criar tarefas de decisao com criterios.
- [ ] Criar tarefas de conhecimento instavel que devem escalar.
- [ ] Implementar judge deterministico por keywords, formato e constraints.
- [ ] Medir taxa de acceptable/partial/fail.
- [ ] Integrar categorias no report.
- [ ] Garantir que stdout do runner continua limpo.
- [ ] Documentar limites do judge semantico.

## Criterios de aceite

- O semantic eval roda sem modelo externo.
- O relatorio diferencia exact match de aceitabilidade semantica.
- O harness nao substitui scoring oficial, mas melhora calibracao.
- Erros abertos aparecem como classes interpretaveis.

## Metricas

- Semantic acceptable rate.
- Partial rate.
- Format fail rate.
- Unsafe/hallucination flags.
- Average answer length.

## Comandos esperados

```bash
python3 scripts/run_semantic_eval.py --check --report reports/generated/semantic-eval.md
python3 -m unittest tests.test_semantic_validation
```

## Riscos

- Criar falso conforto com rubrica fraca.
- Fazer keyword matching simplista demais.
- Confundir judge offline com avaliador oficial.

## Decisao

O semantic harness e um sensor de risco, nao juiz final. Ele deve favorecer explicabilidade e estabilidade.

## Definition of Done

- Dataset semantico existe.
- Rubricas versionadas existem.
- Script e testes passam.
- Battle/readiness pode consumir sinal semantico se o score for util.
