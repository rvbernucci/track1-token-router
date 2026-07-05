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

- [x] Criar interface `OfficialAdapter`.
- [x] Criar adapter `plain_text`.
- [x] Criar adapter `json_task`.
- [x] Criar adapter `jsonl_batch`.
- [x] Criar adapter `file_payload`.
- [x] Criar fixture de exemplo por formato.
- [x] Criar testes de round-trip.
- [x] Documentar como adaptar em 30 minutos.
- [x] Criar `KICKOFF_CHECKLIST.md`.
- [x] Garantir que o core nao conhece detalhes oficiais.

## Criterios de aceite

- [x] Um novo formato pode ser adicionado sem mexer na cascata.
- [x] Testes provam entrada -> `TaskEnvelope` -> saida final.
- [x] O checklist de kickoff explica exatamente onde editar.

## Evidencias

- `router/adapters/official/README.md`
- `fixtures/official/`
- `KICKOFF_CHECKLIST.md`
- `tests/test_official_adapters.py`
- `python3 -m unittest discover -s tests`

## Resultado

Adapters prontos:

- `plain_text`
- `json_task`
- `jsonl_batch`
- `file_payload`

O core permanece isolado: `router/core` nao importa `router.adapters.official`.

## Riscos

- Tentar prever demais o formato oficial.
- Acoplar adapter ao evaluator antes de conhecer o contrato real.

## Saida esperada

Um ponto de encaixe claro para o kickoff, sem interromper a rota offline.
