# Sprint 36 - Submission Rehearsal And Log Redaction

## Tipo

Nao depende de credito.

## Objetivo

Executar um ensaio completo de submissao e endurecer a redacao de logs/traces para que nenhum artefato compartilhavel vaze prompts longos, paths locais, IPs privados, hostnames ou tokens.

## Por que importa

O projeto ja tem reports publicos sanitizados, mas ainda ha logs internos e traces com candidatos crus. Antes de gravar video, publicar demo ou enviar materiais, precisamos separar o que e interno do que e compartilhavel.

## Tese

Uma submissao forte nao e so codigo passando. E um ritual reproduzivel: demo, comandos, video, reports, checklist, CI e artefatos sem vazamento.

## Entregaveis

- `scripts/redact_logs.py`.
- `reports/public/traces/` ou `reports/public/trace-summary.md`.
- `docs/SUBMISSION_REHEARSAL.md`.
- `reports/generated/submission-rehearsal.md`.
- Checklist de video preenchivel.
- Testes de redaction para logs JSONL.

## Checklist

- [x] Mapear campos sensiveis em logs e traces.
- [x] Redigir prompts longos acima de limite configuravel.
- [x] Redigir candidates longos acima de limite configuravel.
- [x] Mascarar paths locais absolutos.
- [x] Bloquear IPs privados.
- [x] Bloquear hostnames privados.
- [x] Bloquear tokens e env assignments.
- [x] Gerar trace summary publico.
- [x] Criar rehearsal script/runbook de 5 minutos.
- [x] Rodar comandos do video em ordem.
- [x] Medir duracao estimada do video.
- [x] Validar audio/tela/terminal como checklist.
- [x] Atualizar `submission/final-checklist.md`.

## Criterios de aceite

- Logs publicaveis passam secret scan e redaction check.
- Ensaio de submissao gera relatorio.
- O roteiro de video cabe em 5 minutos.
- O time sabe exatamente o que abrir, rodar e mostrar no dia final.

## Metricas

- Numero de campos redigidos.
- Tamanho de trace publico.
- Tempo total do ensaio.
- Itens de checklist pendentes.
- Achados de secret scan.

## Comandos esperados

```bash
python3 scripts/redact_logs.py --check --report reports/generated/redaction-report.md
python3 scripts/submission_rehearsal.py --check --report reports/generated/submission-rehearsal.md
```

## Riscos

- Redigir tanto que o report deixa de explicar a decisao.
- Manter logs internos publicaveis por acidente.
- Fazer ensaio de video tarde demais.

## Decisao

O artefato publico deve explicar decisoes sem expor dados brutos sensiveis. Interno e publico precisam ser caminhos separados.

## Definition of Done

- Redaction de logs existe.
- Ensaio de submissao existe.
- Public trace/report e seguro.
- Checklist final fica acionavel para gravacao e envio.
