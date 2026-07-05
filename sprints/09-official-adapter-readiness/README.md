# Sprint 09 - Official Adapter Readiness

## Tipo

Nao depende de credito.

## Objetivo

Preparar o projeto para adaptar rapidamente o formato oficial de input/output revelado no kickoff, sem refatorar o core.

## Entregaveis

- Pasta `router/adapters/official`.
- Interface de adapter oficial.
- Templates para texto, JSON, JSONL e arquivo.
- Testes de contrato.
- Checklist de kickoff.

## Checklist

- [ ] Criar interface `OfficialAdapter`.
- [ ] Criar adapter `plain_text`.
- [ ] Criar adapter `json_task`.
- [ ] Criar adapter `jsonl_batch`.
- [ ] Criar adapter `file_payload`.
- [ ] Criar fixture de exemplo por formato.
- [ ] Criar testes de round-trip.
- [ ] Documentar como adaptar em 30 minutos.
- [ ] Criar `KICKOFF_CHECKLIST.md`.
- [ ] Garantir que o core nao conhece detalhes oficiais.

## Criterios de aceite

- Um novo formato pode ser adicionado sem mexer na cascata.
- Testes provam entrada -> `TaskEnvelope` -> saida final.
- O checklist de kickoff explica exatamente onde editar.

## Riscos

- Tentar prever demais o formato oficial.
- Acoplar adapter ao evaluator antes de conhecer o contrato real.

## Saida esperada

Um ponto de encaixe claro para o kickoff, sem interromper a rota offline.

