# Sprint 01 - Fundacao e contratos

## Objetivo

Criar a espinha dorsal do projeto: CLI minimo, contratos de entrada/saida, logs estruturados e esqueleto testavel.

Esta sprint nao tenta ganhar o hackathon ainda. Ela impede que a gente se perca quando o kickoff revelar o formato real das tasks.

## Entregaveis

- Pacote Python instalavel localmente.
- CLI com comandos vazios ou semi-funcionais: `ask`, `solve`, `run`, `eval`.
- Contratos `TaskEnvelope`, `AnswerResult`, `RouteDecision`, `TokenUsage`.
- Logger JSONL por task.
- Config por env vars.
- Testes unitarios dos contratos e parsers.

## Checklist

- [x] Criar `pyproject.toml`.
- [x] Criar pacote `router`.
- [x] Criar modulo `router.core.contracts`.
- [x] Criar modulo `router.cli.main`.
- [x] Definir schema de entrada para texto simples.
- [x] Definir schema de entrada para JSON.
- [x] Definir schema de entrada para JSONL.
- [x] Garantir que `stdout` so imprime resposta final.
- [x] Garantir que logs humanos vao para `stderr`.
- [x] Criar logger JSONL em `logs/run.jsonl`.
- [x] Criar testes de serializacao e desserializacao.
- [x] Documentar env vars minimas.

## Criterios de aceite

- [x] `router ask "What is 2+2?"` retorna uma resposta mockada no `stdout`.
- [x] `router solve --json < task.json` parseia o envelope e retorna JSON final.
- [x] `router run --jsonl tasks.jsonl --out output.jsonl` processa multiplas tasks.
- [x] Nenhum log de debug contamina `stdout`.
- [x] Testes passam localmente.

## Evidencias

- `python3 -m unittest discover -s tests`
- `python3 -m router ask "What is 2+2?"`
- `python3 -m router solve --json`
- `python3 -m router run --jsonl tasks.jsonl --out output.jsonl`

## Decisoes tecnicas

- Python sera o core competitivo.
- CLI-first, sem servidor web nesta fase.
- Estrutura orientada a contratos, nao a framework.
- Tudo que puder variar no kickoff deve entrar por adapter.

## Riscos

- Overengineering antes de conhecer o evaluator.
- Misturar formato interno com formato final.
- Criar CLI bonita, mas dificil de rodar no container.

## Saida esperada da sprint

Um runner ainda burro, mas confiavel. A partir daqui, qualquer inteligencia entra por tras de contratos estaveis.
