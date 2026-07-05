# Sprint 35 - Batch Throughput And Timeout Stress

## Tipo

Nao depende de credito.

## Objetivo

Estressar execucao em lote, timeouts, throughput e comportamento sob carga usando fake providers e JSONL grande, sem depender de AMD/Fireworks.

## Por que importa

Se o evaluator vier com lote grande ou timeout agressivo, um runner correto mas lento pode perder. Hoje temos latency drill; falta stress de volume, falha parcial e limites de tempo por lote.

## Tese

Performance competitiva nao e apenas p95 de uma task. E estabilidade sob lote, falha parcial e deadline.

## Entregaveis

- `scripts/batch_stress.py`.
- `fixtures/stress/`.
- `reports/generated/batch-stress.md`.
- Configuracao de timeouts por env.
- Testes para lote grande, falha parcial e saida JSONL limpa.
- Opcional: modo concorrente controlado para rotas sem estado.

## Checklist

- [ ] Criar fixture JSONL com 1k tarefas sinteticas pequenas.
- [ ] Criar fixture com mistura de facil, formato, adversarial e conhecimento instavel.
- [ ] Simular provider local lento.
- [ ] Simular provider local com erro intermitente.
- [ ] Simular Fireworks lento em dry-run/fake provider.
- [ ] Medir throughput tasks/s.
- [ ] Medir tempo total por lote.
- [ ] Medir p50/p95/p99 por task.
- [ ] Medir falhas controladas versus crashes.
- [ ] Validar que output JSONL preserva ids e ordem quando necessario.
- [ ] Validar que stderr pode conter diagnostico, mas stdout nao suja resposta.
- [ ] Definir threshold de lote para CI.

## Criterios de aceite

- Stress roda localmente sem creditos.
- O script falha quando timeout/throughput sai do envelope.
- Falhas parciais sao registradas sem quebrar contrato de saida.
- O relatorio identifica gargalos.

## Metricas

- Tasks por segundo.
- Batch elapsed ms.
- p95/p99 por task.
- Error rate.
- Timeout rate.
- Output contract pass rate.

## Comandos esperados

```bash
python3 scripts/batch_stress.py --check --report reports/generated/batch-stress.md
python3 -m unittest tests.test_batch_stress
```

## Riscos

- Otimizar para throughput e quebrar simplicidade do evaluator.
- Introduzir concorrencia antes de provar que o runner e stateless.
- Fazer o CI ficar lento demais.

## Decisao

O primeiro stress deve ser sequencial e deterministico. Concorrencia entra apenas se a medicao provar necessidade.

## Definition of Done

- Stress de lote existe.
- Thresholds sao configuraveis.
- Report mostra gargalos.
- CI continua rapido e estavel.
