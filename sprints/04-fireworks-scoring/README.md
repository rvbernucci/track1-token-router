# Sprint 04 - Fireworks e scoring

## Objetivo

Adicionar Fireworks como auditor remoto de alta potencia e criar o harness de avaliacao que mede qualidade, tokens, latencia e rotas.

Aqui a pergunta deixa de ser "funciona?" e vira "ganha ponto?".

## Entregaveis

- Cliente Fireworks OpenAI-compatible.
- Prompt compacto do auditor remoto.
- Token accounting remoto.
- Eval harness com JSONL.
- Golden set inicial.
- Relatorio de rotas e custo.
- Calibracao do threshold de escalada.

## Checklist

- [x] Criar `FireworksClient`.
- [x] Configurar `FIREWORKS_API_KEY`, `FIREWORKS_BASE_URL`, `FIREWORKS_MODEL`.
- [x] Criar prompt `fireworks_audit_or_replace`.
- [x] Enviar pacote compacto: task, M1, M2B, concern.
- [x] Nao enviar reasoning interno ou rubrica longa.
- [x] Parsear decisao `approve/replace`.
- [x] Registrar tokens de prompt, completion e total.
- [x] Registrar latencia remota.
- [x] Criar comando `router eval`.
- [x] Criar golden set com tarefas faceis, medias, dificeis e adversariais.
- [x] Criar metricas por rota.
- [x] Criar relatorio local em JSON/Markdown.

## Schema Fireworks alvo

```json
{
  "decision": "approve",
  "answer": "",
  "reason": "short reason"
}
```

Regras:

- `approve`: usar resposta do M2B; `answer` fica vazio.
- `replace`: usar `answer` como resposta final.
- `reason`: curto, apenas para log.

## Criterios de aceite

- [x] Fireworks so e chamado quando M2A escala.
- [x] Tokens remotos sao registrados por task.
- [x] O eval mostra accuracy aproximada, custo remoto e distribuicao de rotas.
- [x] O pacote enviado ao Fireworks e compacto.
- [x] O runner consegue operar sem Fireworks em modo local-only.

## Evidencias

- `python3 -m unittest discover -s tests`
- `ROUTER_MODE=hybrid LOCAL_BASE_URL=<local-url> LOCAL_MODEL=<local-model> FIREWORKS_API_KEY=<key> FIREWORKS_MODEL=<fw-model> python3 -m router ask "What is 2+2?"`
- `python3 -m router eval --jsonl evals/golden/tasks.jsonl --expected evals/golden/expected.jsonl --report reports/generated/golden-report.md`
- `evals/golden/tasks.jsonl`
- `evals/golden/expected.jsonl`

## Metricas essenciais

- `remote_prompt_tokens`
- `remote_completion_tokens`
- `remote_total_tokens`
- `route`
- `latency_m1_ms`
- `latency_m2a_ms`
- `latency_m2b_ms`
- `latency_fireworks_ms`
- `final_answer_chars`
- `parse_failures`
- `escalation_rate`
- `replacement_rate`

## Experimentos de calibracao

- Threshold conservador: escala mais, erra menos, gasta mais.
- Threshold agressivo: escala menos, gasta menos, arrisca accuracy.
- Fireworks auditando M1 direto vs auditando M2B.
- Fireworks com resposta curta vs resposta completa.
- Pacote com M2A reason vs sem M2A reason.

## Riscos

- Auditor remoto aprovar resposta ruim para economizar tokens.
- Auditor remoto substituir demais e aumentar custo.
- Prompt remoto ficar grande e destruir vantagem.
- Avaliacao local nao representar scoring oficial.

## Saida esperada da sprint

Um sistema mensuravel, com custo remoto controlado e calibracao baseada em dados, nao em intuicao.
