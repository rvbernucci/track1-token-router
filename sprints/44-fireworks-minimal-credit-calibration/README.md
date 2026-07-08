# Sprint 44 - Fireworks Minimal Credit Calibration

## Tipo

Depende parcialmente de credito Fireworks, mas tem preparacao offline.

## Objetivo

Usar o minimo possivel de credito para calibrar a matriz Pareto/Game Theory com chamadas reais: poucos prompts, max tokens baixo, modelos selecionados e medicao real de token/latencia.

## Tese

Benchmarks publicos ajudam, mas o scoring do hackathon depende do comportamento real no endpoint Fireworks. Precisamos de uma amostra pequena, controlada e barata para corrigir preco estimado, latencia e tendencia de output.

## Entregaveis

- `evals/fireworks-pareto/minimal-credit-sample.jsonl`.
- Script `scripts/fireworks_minimal_calibration.py`.
- Budget guard obrigatorio em dolares e numero maximo de chamadas.
- Relatorio `reports/generated/fireworks-minimal-calibration.md`.
- Patch de calibracao em perfis do roteador, se os dados justificarem.

## Checklist Offline

- [ ] Selecionar 2 prompts por dominio critico.
- [ ] Definir `max_tokens` curto por tipo de tarefa.
- [ ] Definir budget hard cap.
- [ ] Garantir dry-run que imprime plano sem chamar API.
- [ ] Garantir que `.env.fireworks.local` nunca aparece em log.
- [ ] Testar com fake provider.

## Checklist Com Credito

- [ ] Rodar smoke com 1 prompt cheap.
- [ ] Rodar amostra minima por modelos candidatos.
- [ ] Capturar tokens reais de prompt/completion.
- [ ] Capturar latencia real.
- [ ] Comparar escolha esperada vs resultado real.
- [ ] Atualizar perfis apenas se houver evidencia.
- [ ] Re-rodar replay offline com os novos parametros.

## Metricas

- total calls;
- total estimated cost;
- total real tokens;
- latency p50/p95;
- output token drift;
- failure rate;
- model rejection of request options;
- accuracy proxy/manual pass rate.

## Definition Of Done

- A calibracao real custa pouco e e reproduzivel.
- Existe dry-run seguro.
- Os parametros do roteador sao atualizados somente por evidencia.
- O relatorio mostra o que mudou e por que.

## Anti-Escopo

- Nao rodar benchmark grande com credito limitado.
- Nao testar todos os modelos em todos os prompts.
- Nao aumentar `max_tokens` sem justificativa.
- Nao usar priority/fast sem motivo explicito.
