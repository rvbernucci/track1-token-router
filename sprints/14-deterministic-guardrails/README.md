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

- [x] Detectar input vazio.
- [x] Detectar saudacoes simples.
- [x] Detectar contas triviais de soma/subtracao seguras.
- [x] Detectar pedido de eco literal.
- [x] Nao resolver matematica complexa.
- [x] Criar `GuardedRunner`.
- [x] Adicionar config `ENABLE_GUARDRAILS`.
- [x] Integrar sem quebrar modos existentes.
- [x] Adicionar testes.
- [x] Documentar limites.

## Criterios de aceite

- Guardrails podem ser ligados/desligados por env var.
- Casos deterministiscos saem sem chamada de modelo.
- Casos complexos passam para o runner normal.
- Testes provam que a camada e conservadora.

## Saida esperada

Economia local/remota em tarefas triviais, sem transformar regex em motor de raciocinio.

## Evidencia local

```bash
python3 -m unittest tests.test_guardrails
ENABLE_GUARDRAILS=1 python3 -m router ask "What is 12 - 5? Return only the number." --json
scripts/offline_release_check.sh
```

## Limites

- Nao resolve multiplicacao, divisao, porcentagem, algebra, datas ou problemas de palavras.
- Nao tenta julgar dificuldade ampla.
- Na arquitetura atual, `sub_intent`, `deterministic_fit` e a regressao tornam o solver candidato; ele ainda precisa aceitar o input original.
