# Sprint 08 - Fake Provider Chaos Lab

## Tipo

Nao depende de credito.

## Objetivo

Criar simuladores configuraveis de provedor local e Fireworks para testar falhas, latencia, timeout, respostas ruins, JSON invalido e token usage sem gastar credito.

## Entregaveis

- Fake provider executavel fora dos testes.
- Perfis de comportamento: happy path, slow, flaky, invalid JSON, wrong answer, high token usage.
- Testes de resiliencia por perfil.
- Relatorio de robustez.
- Documentacao para rodar a cascata contra provedores falsos.

## Checklist

- [ ] Transformar `tests/fake_openai_server.py` em utilitario reutilizavel.
- [ ] Criar CLI `python3 -m router.dev.fake_provider`.
- [ ] Suportar respostas em sequencia.
- [ ] Suportar atraso artificial.
- [ ] Suportar erro HTTP configuravel.
- [ ] Suportar usage tokens configuravel.
- [ ] Criar cenarios de Fireworks approve/replace.
- [ ] Criar cenarios de JSON invalido.
- [ ] Criar teste de timeout end-to-end.
- [ ] Criar doc de chaos testing.

## Criterios de aceite

- E possivel rodar `ROUTER_MODE=hybrid` sem credenciais reais usando fake providers.
- O sistema se comporta bem com timeout, erro 500 e JSON invalido.
- Logs mostram falhas sem vazar segredo.
- CI roda ao menos um cenario fake hybrid.

## Riscos

- Simulador ficar mais complexo que o necessario.
- Falso senso de seguranca por testar apenas falhas previsiveis.

## Saida esperada

Uma bancada de teste que simula a guerra antes da guerra.

