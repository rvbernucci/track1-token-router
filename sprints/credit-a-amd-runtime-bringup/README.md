# Credit Sprint A - AMD Runtime Bring-up

## Tipo

Depende de credito AMD Developer Cloud.

## Objetivo

Subir o modelo local real em GPU AMD e expor um endpoint OpenAI-compatible para o roteador.

## Gatilho

Comecar apenas quando houver acesso real a AMD Developer Cloud.

## Checklist

- [ ] Provisionar instancia GPU AMD.
- [ ] Registrar modelo local escolhido.
- [ ] Subir servidor OpenAI-compatible.
- [ ] Validar `LOCAL_BASE_URL`.
- [ ] Rodar `ROUTER_MODE=local`.
- [ ] Rodar `ROUTER_MODE=cascade`.
- [ ] Medir latencia M1/M2A/M2B.
- [ ] Documentar setup e comandos.

## Criterios de aceite

- O roteador chama modelo local real.
- Logs mostram latencia real.
- O setup pode ser repetido do zero.

