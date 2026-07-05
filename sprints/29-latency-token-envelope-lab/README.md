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

- [x] Medir cold start do CLI `ask`.
- [x] Medir tempo por task em `ROUTER_MODE=competition`.
- [x] Medir tempo por lote JSONL.
- [x] Medir p50, p95 e p99.
- [x] Simular provider local lento.
- [x] Simular Fireworks lento.
- [x] Simular timeout local.
- [x] Simular timeout remoto.
- [x] Criar thresholds configuraveis por env.
- [x] Falhar em `--check` quando p95 exceder limite.
- [x] Calcular tokens estimados por packet remoto.
- [x] Calcular pior caso por rota.
- [x] Gerar top 20 tarefas mais caras.
- [x] Mostrar exposicao remota por policy.
- [x] Integrar `latency_ready` ao battle drill.
- [x] Integrar `token_envelope_ready` ao battle drill.

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

## Evidencias

- `scripts/latency_drill.py --check` mede cold start, tarefas individuais, lote JSONL, p50/p95/p99 e probes de timeout.
- `scripts/token_envelope.py --check` calcula exposicao remota por policy, pior caso por rota e top 20 tarefas mais caras.
- `router/evals/operational_envelope.py` centraliza thresholds e calculos para scripts e battle drill.
- `tests/test_operational_envelope.py` cobre percentis, falha por p95 e thresholds de token.
- `tests/test_battle_drill.py` valida `latency_ready` e `token_envelope_ready`.
- `scripts/offline_release_check.sh` executa os dois labs antes do battle drill.
