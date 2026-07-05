# Competition Gap Analysis

Atualizado em: 2026-07-05

## Contexto

As Sprints 01-21 criaram um runner competitivo com dataset offline, scoring, guardrails, trace analytics, state machine, budget manager, policy engine, prompt packet, final validator e battle drill.

O proximo bloco nao depende de creditos. Ele transforma o projeto em uma submissao pronta para ativar AMD Developer Cloud, DigitalOcean, Gemma, Fireworks e ferramentas parceiras quando os creditos chegarem.

## Gaps restantes sem credito

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

## Ordem recomendada

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

