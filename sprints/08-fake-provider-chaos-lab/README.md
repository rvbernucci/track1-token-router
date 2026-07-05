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

- [x] Transformar `tests/fake_openai_server.py` em utilitario reutilizavel.
- [x] Criar CLI `python3 -m router.dev.fake_provider`.
- [x] Suportar respostas em sequencia.
- [x] Suportar atraso artificial.
- [x] Suportar erro HTTP configuravel.
- [x] Suportar usage tokens configuravel.
- [x] Criar cenarios de Fireworks approve/replace.
- [x] Criar cenarios de JSON invalido.
- [x] Criar teste de timeout end-to-end.
- [x] Criar doc de chaos testing.

## Criterios de aceite

- [x] E possivel rodar `ROUTER_MODE=hybrid` sem credenciais reais usando fake providers.
- [x] O sistema se comporta bem com timeout, erro 500 e JSON invalido.
- [x] Logs mostram falhas sem vazar segredo.
- [x] CI roda ao menos um cenario fake hybrid.

## Evidencias

- `python3 -m router.dev.fake_provider --help`
- `python3 -m unittest discover -s tests`
- `scripts/verify.sh`
- `tests/test_hybrid_cascade.py`
- `tests/test_fake_provider.py`
- `docs/CHAOS_LAB.md`

## Perfis suportados

- `happy`
- `verifier-approve`
- `verifier-escalate`
- `fireworks-approve`
- `fireworks-replace`
- `wrong-answer`
- `--status 500`
- `--delay-s`
- `--invalid-json`
- `--prompt-tokens` e `--completion-tokens`

## Riscos

- Simulador ficar mais complexo que o necessario.
- Falso senso de seguranca por testar apenas falhas previsiveis.

## Saida esperada

Uma bancada de teste que simula a guerra antes da guerra.
