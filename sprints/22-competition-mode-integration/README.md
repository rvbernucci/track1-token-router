# Sprint 22 - Competition Mode Integration

## Tipo

Nao depende de credito.

## Objetivo

Criar um modo unico de competicao que integre guardrails, state machine, risk signals, budget manager, policy engine, prompt packet, final validator e battle trace em um caminho operacional coerente.

## Por que importa

As Sprints 17-21 criaram pecas fortes. Para disputar seriamente, essas pecas precisam virar um modo de execucao plug-and-play, com comportamento previsivel e configuravel por env vars.

## Entregaveis

- `ROUTER_MODE=competition`.
- Runner `CompetitionRunner` ou wrapper equivalente.
- Contrato de decisao unica por task.
- Trace consolidado com policy, budget, validation e route.
- Modo dry-run sem provedores reais.
- Comparacao offline entre `competition` e modos legados.
- Testes end-to-end em CLI e JSONL.

## Checklist

- [x] Definir contrato `CompetitionDecision`.
- [x] Definir contrato `CompetitionTrace`.
- [x] Criar `CompetitionRunner`.
- [x] Ligar guardrails como etapa zero.
- [x] Ligar risk signals antes da decisao.
- [x] Ligar budget decision antes de qualquer remoto.
- [x] Ligar policy engine no caminho quente.
- [x] Ligar final validator sempre antes do output.
- [x] Registrar `final_answer_repaired` quando houver reparo seguro.
- [x] Registrar `remote_packet_tokens` no trace.
- [x] Criar env var `ROUTER_MODE=competition`.
- [x] Criar dry-run que nao chama modelo real.
- [x] Adicionar teste CLI `ask`.
- [x] Adicionar teste JSONL `run`.
- [x] Adicionar teste de stdout limpo.
- [x] Atualizar battle drill para incluir modo `competition`.

## Criterios de aceite

- Um comando executa o modo competicao sem creditos.
- O modo competicao gera resposta final limpa no `stdout`.
- O trace inclui policy, budget, validacao final e rota.
- O modo legado continua passando no CI.
- O battle drill compara o modo competicao contra o baseline.

## Saida esperada

O projeto deixa de ser um conjunto de laboratorios e passa a ter um caminho competitivo unico, pronto para receber endpoints reais.

## Decisao

O modo competicao deve ser opt-in ate provar vantagem no battle drill. Assim protegemos o caminho atual enquanto amadurecemos o runtime final.

## Evidencia de fechamento

- `python3 -m unittest discover -s tests`: 101 testes passando.
- `python3 scripts/battle_drill.py`: `competition_mode_ready=true`.
- `ROUTER_MODE=competition COMPETITION_DRY_RUN=1 python3 -m router ask "What is 10 + 5? Return only the number."`: stdout limpo com `15`.
