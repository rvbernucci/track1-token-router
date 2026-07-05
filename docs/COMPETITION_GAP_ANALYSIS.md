# Competition Gap Analysis

Atualizado em: 2026-07-05

## Contexto

As Sprints 01-21 criaram um runner competitivo com dataset offline, scoring, guardrails, trace analytics, state machine, budget manager, policy engine, prompt packet, final validator e battle drill.

As Sprints 22-26 ja transformaram essas pecas em modo competicao, fuzz pack, solvers deterministicos, runtime profiles e kit de submissao.

O proximo bloco sem credito esta documentado em `docs/NEXT_NO_CREDIT_IMPROVEMENTS.md`. Ele mira demo URL, artefatos finais, adapter drill, latencia, token envelope e replay de decisoes.

## Gaps fechados nas Sprints 22-26

| Gap | Risco | Sprint |
|---|---|---|
| Pecas fortes ainda nao viraram caminho unico de runtime competitivo. | A solucao fica parecendo laboratorio, nao runner final. | Sprint 22 |
| Formato oficial de input/output pode surpreender. | Adapter quebra no kickoff ou no scoring. | Sprint 23 |
| Tarefas mecanicas ainda podem cair em LLM. | Latencia e erro desnecessario. | Sprint 24 |
| Plataformas oficiais estao mapeadas, mas nao viraram runbooks executaveis. | Creditos chegam e ainda perdemos tempo operacional. | Sprint 25 |
| Submissao lablab exige artefatos alem do codigo. | Projeto bom, submissao fraca. | Sprint 26 |

## Principio

Cada sprint precisa responder a pelo menos uma pergunta:

- reduz risco de scoring?
- reduz token remoto?
- melhora accuracy?
- melhora reproducibilidade?
- acelera ativacao quando os creditos chegarem?
- melhora chance de submissao completa?

Se a resposta for nao, nao entra nesta trilha.

## Ordem executada

1. `Sprint 22 - Competition Mode Integration`
2. `Sprint 23 - Official Input Fuzz Pack`
3. `Sprint 24 - Deterministic Solver Pack`
4. `Sprint 25 - Platform Runbooks & Runtime Profiles`
5. `Sprint 26 - Submission Readiness Kit`

## Resultado esperado

Ao final da Sprint 26, o projeto deve estar pronto para:

- rodar em modo competicao offline;
- adaptar input oficial rapidamente;
- resolver tarefas mecanicas sem modelo;
- ativar AMD/Fireworks com env profiles;
- submeter no lablab com narrativa, artefatos e checklist fortes.

## Status pos Sprint 26

- `ROUTER_MODE=competition` existe e roda sem creditos.
- Fuzz pack cobre formatos e erros controlados.
- Solver pack evita LLM em tarefas mecanicas.
- Runbooks e runtime profiles estao prontos para AMD/DigitalOcean, Gemma, Fireworks e Native.Builder auxiliar.
- Submission kit e readiness check estao prontos.
- Proxima prioridade sem credito: transformar readiness tecnica em demo/submissao impossivel de interpretar errado.
