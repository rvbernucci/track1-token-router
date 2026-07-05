# Sprint 20 - Compact Prompt Packet & Final Validator

## Tipo

Nao depende de credito.

## Objetivo

Padronizar o pacote minimo enviado ao auditor remoto e adicionar um validador final de formato antes de devolver a resposta.

## Por que importa

O remoto deve ser usado como seguro, nao como conversa longa. E resposta certa no formato errado pode valer como erro.

## Entregaveis

- Modulo `router/orchestration/prompt_packet.py`.
- Modulo `router/orchestration/final_validator.py`.
- Contrato `RemoteAuditPacket`.
- Contrato `FinalValidationResult`.
- Medidor de tamanho do pacote.
- Validadores de formato comum.
- Testes de JSON, numero puro, eco literal e texto livre.

## Checklist

- [x] Definir pacote remoto minimo: task, candidato, concern, formato esperado.
- [x] Remover informacao redundante do pacote.
- [x] Medir caracteres e tokens estimados do pacote.
- [x] Validar resposta JSON quando a task pede JSON.
- [x] Validar numero puro quando a task pede numero.
- [x] Validar eco literal quando a task pede texto exato.
- [x] Validar resposta vazia indevida.
- [x] Validar excesso de markdown em formato estrito.
- [x] Adicionar reparo local simples quando formato falhar.
- [x] Integrar falha de formato ao trace.
- [x] Integrar tamanho do packet ao scoreboard.
- [x] Adicionar testes de regressao.

## Criterios de aceite

- O pacote remoto e menor que o prompt bruto equivalente.
- O validador final bloqueia formatos obviamente errados.
- Falhas de formato viram sinal para policy/budget.
- A resposta final continua livre quando a task nao exige formato estrito.

## Saida esperada

Menos token remoto e menos perda boba por formato.

## Evidencia local

```bash
python3 -m unittest tests.test_prompt_packet_and_validator
python3 scripts/offline_score_simulator.py
ENABLE_ORCHESTRATOR=1 python3 -m router ask "Return exactly SAFE_OUTPUT and nothing else." --json
scripts/offline_release_check.sh
```

## Decisao

O pacote remoto fica em `RemoteAuditPacket` com apenas task compactada, candidato, concern e formato esperado. O validador final roda dentro do `OrchestratedRunner` quando o orquestrador esta ligado, sem mudar o caminho padrao.
