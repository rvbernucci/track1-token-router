# Sprint 25 - Platform Runbooks & Runtime Profiles

## Tipo

Nao depende de credito.

## Objetivo

Transformar a documentacao oficial de AMD Developer Cloud, DigitalOcean, Gemma, Fireworks e Native.Builder em runbooks executaveis e perfis de runtime prontos para ativacao.

## Por que importa

Quando os creditos chegarem, nao podemos gastar as primeiras horas decidindo comandos, portas, env vars e health checks. Tudo que pode ser preparado offline deve estar pronto.

## Entregaveis

- `runtime-profiles/`.
- Perfis `.env.example` por plataforma/modelo.
- Runbook AMD/DigitalOcean MI300X.
- Runbook vLLM OpenAI-compatible.
- Runbook SGLang OpenAI-compatible.
- Runbook Gemma local.
- Runbook Fireworks serverless.
- Runbook Native.Builder como demo auxiliar.
- Health check offline para perfis.
- Checklist de custo e destruicao de VM.

## Checklist

- [x] Criar `runtime-profiles/amd-mi300x-vllm.env.example`.
- [x] Criar `runtime-profiles/amd-mi300x-sglang.env.example`.
- [x] Criar `runtime-profiles/gemma-local.env.example`.
- [x] Criar `runtime-profiles/fireworks-serverless.env.example`.
- [x] Criar `docs/RUNBOOK_AMD_DIGITALOCEAN.md`.
- [x] Criar `docs/RUNBOOK_GEMMA.md`.
- [x] Criar `docs/RUNBOOK_FIREWORKS.md`.
- [x] Criar `docs/RUNBOOK_NATIVE_BUILDER.md`.
- [x] Documentar portas, comandos e health checks.
- [x] Documentar variaveis obrigatorias e opcionais.
- [x] Documentar estrategia de scratch disk.
- [x] Documentar regra de destruir VM para parar custo.
- [x] Criar script `scripts/check_runtime_profiles.py`.
- [x] Validar que nenhum perfil contem segredo real.
- [x] Integrar profile check ao release check.
- [x] Atualizar `CREDIT_ACTIVATION.md`.

## Criterios de aceite

- Cada plataforma oficial tem um runbook claro.
- Cada perfil pode ser validado sem credenciais.
- O time consegue ativar AMD/Fireworks sem redesenhar arquitetura.
- Nenhum segredo real aparece em docs, envs ou CI.

## Saida esperada

Creditos deixam de ser bloqueio operacional e viram apenas troca de env vars.

## Decisao

Runbooks devem ser comandos reproduziveis, nao anotacoes soltas. O objetivo e reduzir tempo de ativacao no kickoff.

## Evidencia de fechamento

- `python3 scripts/check_runtime_profiles.py`: perfis validos e sem segredo real.
- `python3 -m unittest tests.test_runtime_profiles`: validador CLI e deteccao de segredo sintetico testados.
- `python3 scripts/secret_scan.py`: scanner global sem achados.
- `scripts/offline_release_check.sh`: profile check integrado a porteira pesada.
