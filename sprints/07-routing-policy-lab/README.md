# Sprint 07 - Routing Policy Lab

## Tipo

Nao depende de credito.

## Objetivo

Transformar a decisao de roteamento em politica calibravel, com modos claros para comparar accuracy, custo remoto simulado e taxa de escalada.

## Entregaveis

- Modos `aggressive`, `balanced`, `conservative`.
- Configuracao por `ROUTER_POLICY`.
- Relatorio comparando politicas no dataset offline.
- Ablation tests de M2A.
- Registro de decisao tecnica da politica padrao.

## Checklist

- [x] Adicionar `ROUTER_POLICY`.
- [x] Definir thresholds por politica.
- [x] Criar prompt M2A por politica ou parametros de decisao.
- [x] Medir escalation rate por politica.
- [x] Medir replacement rate simulado por politica.
- [x] Medir exact match por politica.
- [x] Criar comando ou script de comparacao.
- [x] Gerar relatorio Markdown de Pareto.
- [x] Escolher politica default temporaria.
- [x] Documentar quando usar cada modo.

## Criterios de aceite

- [x] O mesmo dataset roda em pelo menos tres politicas.
- [x] O relatorio mostra tradeoff entre qualidade e custo.
- [x] A politica default e escolhida por metrica, nao por intuicao.
- [x] Nenhuma politica exige credenciais reais.

## Politicas

- `aggressive`: minimiza custo remoto simulado; aceita mais risco local.
- `balanced`: politica temporaria padrao; melhor Pareto no dataset offline atual.
- `conservative`: escala mais; preserva qualidade simulada com custo remoto maior.

## Evidencias

- `python3 scripts/compare_policies.py --jsonl evals/offline/tasks.jsonl --expected evals/offline/expected.jsonl --report reports/generated/policy-comparison.md`
- `python3 -m unittest discover -s tests`
- `scripts/verify.sh`

## Resultado offline atual

| Politica | Exact match | Escalation rate | Replacement rate | Tokens remotos simulados |
|---|---:|---:|---:|---:|
| `aggressive` | `0.75` | `0.375` | `0.0` | `0` |
| `balanced` | `1.0` | `0.5` | `0.125` | `5600` |
| `conservative` | `1.0` | `0.625` | `0.5` | `22400` |

Decisao temporaria: `balanced` fica como default porque preserva accuracy simulada com custo menor que `conservative` e melhor match de rota esperada que `aggressive`.

## Riscos

- Criar heuristica bonita que nao melhora metricas.
- Otimizar demais para dataset artificial.
- Escalar demais e esconder fragilidade do M2A.

## Saida esperada

Um laboratorio de roteamento que nos permite buscar Pareto offline.
