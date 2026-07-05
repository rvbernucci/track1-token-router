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

- [ ] Adicionar `ROUTER_POLICY`.
- [ ] Definir thresholds por politica.
- [ ] Criar prompt M2A por politica ou parametros de decisao.
- [ ] Medir escalation rate por politica.
- [ ] Medir replacement rate simulado por politica.
- [ ] Medir exact match por politica.
- [ ] Criar comando ou script de comparacao.
- [ ] Gerar relatorio Markdown de Pareto.
- [ ] Escolher politica default temporaria.
- [ ] Documentar quando usar cada modo.

## Criterios de aceite

- O mesmo dataset roda em pelo menos tres politicas.
- O relatorio mostra tradeoff entre qualidade e custo.
- A politica default e escolhida por metrica, nao por intuicao.
- Nenhuma politica exige credenciais reais.

## Riscos

- Criar heuristica bonita que nao melhora metricas.
- Otimizar demais para dataset artificial.
- Escalar demais e esconder fragilidade do M2A.

## Saida esperada

Um laboratorio de roteamento que nos permite buscar Pareto offline.

