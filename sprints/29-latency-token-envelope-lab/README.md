# Sprint 29 - Latency And Token Envelope Lab

## Tipo

Nao depende de credito.

## Objetivo

Criar laboratorios offline para medir latencia, timeout, cold start, throughput JSONL e exposicao conservadora de tokens remotos.

## Por que importa

Uma resposta correta pode perder se for lenta, instavel ou cara. Antes de ter AMD/Fireworks reais, ainda podemos medir o envelope operacional do runner, simular atrasos e detectar rotas que tendem a estourar budget.

## Tese

O battle drill deve evoluir de "esta pronto?" para "esta pronto dentro de um envelope de tempo e token?".

## Entregaveis

- `scripts/latency_drill.py`.
- `scripts/token_envelope.py`.
- `reports/generated/latency-report.md`.
- `reports/generated/token-envelope.md`.
- Integracao de readiness no battle drill.
- Testes de p95, timeout simulado e ranking de prompts caros.

## Checklist

- [ ] Medir cold start do CLI `ask`.
- [ ] Medir tempo por task em `ROUTER_MODE=competition`.
- [ ] Medir tempo por lote JSONL.
- [ ] Medir p50, p95 e p99.
- [ ] Simular provider local lento.
- [ ] Simular Fireworks lento.
- [ ] Simular timeout local.
- [ ] Simular timeout remoto.
- [ ] Criar thresholds configuraveis por env.
- [ ] Falhar em `--check` quando p95 exceder limite.
- [ ] Calcular tokens estimados por packet remoto.
- [ ] Calcular pior caso por rota.
- [ ] Gerar top 20 tarefas mais caras.
- [ ] Mostrar exposicao remota por policy.
- [ ] Integrar `latency_ready` ao battle drill.
- [ ] Integrar `token_envelope_ready` ao battle drill.

## Criterios de aceite

- `latency_drill.py --check` passa no ambiente local.
- `token_envelope.py --check` passa sem Fireworks.
- Relatorios mostram limites, resultados e riscos.
- Battle drill inclui readiness de latencia e token envelope.
- Nenhuma medicao depende de credito real.

## Metricas

- CLI cold start.
- p50/p95/p99 por task.
- throughput de JSONL tasks por segundo.
- packet tokens medio e maximo.
- remote token exposure por policy.
- numero de tasks acima do budget por task.

## Comandos esperados

```bash
python3 scripts/latency_drill.py --check --report reports/generated/latency-report.md
python3 scripts/token_envelope.py --check --report reports/generated/token-envelope.md
python3 scripts/battle_drill.py
```

## Riscos

- Confundir latencia offline com latencia real de GPU.
- Criar thresholds impossiveis para CI.
- Otimizar cold start local e esquecer batch/evaluator.

## Decisao

O sprint mede envelopes e tendencias. Benchmarks reais de AMD/Fireworks continuam na trilha dependente de credito.

## Definition of Done

- Latency drill existe e tem `--check`.
- Token envelope existe e tem `--check`.
- Reports sao gerados.
- Battle drill consome os sinais.
- CI continua estavel.
