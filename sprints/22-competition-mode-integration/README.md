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

- [ ] Definir contrato `CompetitionDecision`.
- [ ] Definir contrato `CompetitionTrace`.
- [ ] Criar `CompetitionRunner`.
- [ ] Ligar guardrails como etapa zero.
- [ ] Ligar risk signals antes da decisao.
- [ ] Ligar budget decision antes de qualquer remoto.
- [ ] Ligar policy engine no caminho quente.
- [ ] Ligar final validator sempre antes do output.
- [ ] Registrar `final_answer_repaired` quando houver reparo seguro.
- [ ] Registrar `remote_packet_tokens` no trace.
- [ ] Criar env var `ROUTER_MODE=competition`.
- [ ] Criar dry-run que nao chama modelo real.
- [ ] Adicionar teste CLI `ask`.
- [ ] Adicionar teste JSONL `run`.
- [ ] Adicionar teste de stdout limpo.
- [ ] Atualizar battle drill para incluir modo `competition`.

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

