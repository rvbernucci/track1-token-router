# Sprint 14 - Deterministic Guardrails

## Tipo

Nao depende de credito.

## Objetivo

Adicionar uma camada deterministica opcional antes da cascata para resolver ou bloquear casos obvios sem chamar LLM local ou remota.

## Entregaveis

- Modulo `router/core/guardrails.py`.
- Regras deterministicas seguras.
- Wrapper de runner com guardrails.
- Config `ENABLE_GUARDRAILS`.
- Testes de cada regra.
- Logs indicando rota deterministica.

## Checklist

- [ ] Detectar input vazio.
- [ ] Detectar saudacoes simples.
- [ ] Detectar contas triviais de soma/subtracao seguras.
- [ ] Detectar pedido de eco literal.
- [ ] Nao resolver matematica complexa.
- [ ] Criar `GuardedRunner`.
- [ ] Adicionar config `ENABLE_GUARDRAILS`.
- [ ] Integrar sem quebrar modos existentes.
- [ ] Adicionar testes.
- [ ] Documentar limites.

## Criterios de aceite

- Guardrails podem ser ligados/desligados por env var.
- Casos deterministiscos saem sem chamada de modelo.
- Casos complexos passam para o runner normal.
- Testes provam que a camada e conservadora.

## Saida esperada

Economia local/remota em tarefas triviais, sem transformar regex em motor de raciocinio.

