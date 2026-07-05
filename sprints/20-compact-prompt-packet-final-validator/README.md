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

- [ ] Definir pacote remoto minimo: task, candidato, concern, formato esperado.
- [ ] Remover informacao redundante do pacote.
- [ ] Medir caracteres e tokens estimados do pacote.
- [ ] Validar resposta JSON quando a task pede JSON.
- [ ] Validar numero puro quando a task pede numero.
- [ ] Validar eco literal quando a task pede texto exato.
- [ ] Validar resposta vazia indevida.
- [ ] Validar excesso de markdown em formato estrito.
- [ ] Adicionar reparo local simples quando formato falhar.
- [ ] Integrar falha de formato ao trace.
- [ ] Integrar tamanho do packet ao scoreboard.
- [ ] Adicionar testes de regressao.

## Criterios de aceite

- O pacote remoto e menor que o prompt bruto equivalente.
- O validador final bloqueia formatos obviamente errados.
- Falhas de formato viram sinal para policy/budget.
- A resposta final continua livre quando a task nao exige formato estrito.

## Saida esperada

Menos token remoto e menos perda boba por formato.

