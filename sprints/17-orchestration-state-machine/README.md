# Sprint 17 - Orchestration State Machine

## Tipo

Nao depende de credito.

## Objetivo

Transformar a cascata em uma state machine explicita, com estados, transicoes, razoes de decisao e fallbacks previsiveis.

## Por que importa

Competicao nao premia arquitetura bonita; premia comportamento repetivel sob pressao. A state machine evita que decisao critica fique espalhada entre prompts, ifs e efeitos colaterais.

## Entregaveis

- Modulo `router/orchestration/state_machine.py`.
- Enum/lista de estados canonicos.
- Registro estruturado de cada transicao.
- Mapa de fallback por erro.
- Runner orquestrado atras de feature flag ou modo novo.
- Testes de transicoes felizes e falhas.
- Relatorio local de rotas por estado.

## Checklist

- [x] Definir estados: `received`, `guardrail`, `m1_candidate`, `local_verify`, `local_repair`, `remote_audit`, `final`, `failed`.
- [x] Definir eventos de transicao: `approve`, `escalate`, `replace`, `fallback`, `error`.
- [x] Criar contrato `OrchestrationTrace`.
- [x] Criar contrato `OrchestrationStep`.
- [x] Integrar guardrails como primeiro estado opcional.
- [x] Integrar M1/M2A/M2B/Fireworks sem duplicar logica existente.
- [x] Definir fallback para erro local.
- [x] Definir fallback para erro remoto.
- [x] Definir fallback para parse invalido.
- [x] Adicionar testes de transicao.
- [x] Adicionar teste de trace completo.
- [x] Documentar diagrama da state machine.

## Criterios de aceite

- Cada resposta final tem historico de estados.
- Nenhum erro conhecido deixa a task sem rota final.
- A cascata existente continua funcionando.
- A state machine pode ser testada offline com fake providers.

## Saida esperada

Um orquestrador previsivel, auditavel e pronto para receber politicas mais inteligentes.

## Diagrama

```text
received
  -> guardrail
      -> final
  -> m1_candidate
      -> local_verify
          -> final
          -> local_repair
              -> final
              -> remote_audit
                  -> final
                  -> failed -> final
```

## Evidencia local

```bash
ENABLE_ORCHESTRATOR=1 ENABLE_GUARDRAILS=1 python3 -m router ask "What is 10 + 5?" --json
python3 scripts/state_machine_report.py
python3 -m unittest tests.test_state_machine
scripts/offline_release_check.sh
```

## Decisao

O `OrchestratedRunner` envolve os runners existentes e infere estados a partir da rota final. Isso evita duplicar a logica M1/M2A/M2B/Fireworks agora, mas ja entrega trace estruturado para policy, budget e battle drill nas proximas sprints.
