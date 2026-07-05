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

- [ ] Definir estados: `received`, `guardrail`, `m1_candidate`, `local_verify`, `local_repair`, `remote_audit`, `final`, `failed`.
- [ ] Definir eventos de transicao: `approve`, `escalate`, `replace`, `fallback`, `error`.
- [ ] Criar contrato `OrchestrationTrace`.
- [ ] Criar contrato `OrchestrationStep`.
- [ ] Integrar guardrails como primeiro estado opcional.
- [ ] Integrar M1/M2A/M2B/Fireworks sem duplicar logica existente.
- [ ] Definir fallback para erro local.
- [ ] Definir fallback para erro remoto.
- [ ] Definir fallback para parse invalido.
- [ ] Adicionar testes de transicao.
- [ ] Adicionar teste de trace completo.
- [ ] Documentar diagrama da state machine.

## Criterios de aceite

- Cada resposta final tem historico de estados.
- Nenhum erro conhecido deixa a task sem rota final.
- A cascata existente continua funcionando.
- A state machine pode ser testada offline com fake providers.

## Saida esperada

Um orquestrador previsivel, auditavel e pronto para receber politicas mais inteligentes.

