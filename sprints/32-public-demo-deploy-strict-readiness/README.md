# Sprint 32 - Public Demo Deploy And Strict Readiness

## Tipo

Nao depende de credito.

## Objetivo

Publicar a demo estatica em uma URL real, fechar os campos publicos de submissao que nao dependem de AMD/Fireworks e transformar o modo `--strict` em um gate confiavel de pre-submissao.

## Por que importa

O projeto ja tem `demo-site/`, reports publicos, CI verde e artefatos finais. Ainda assim, a submissao lablab pede uma experiencia acessivel por URL. Sem uma URL publica testada, a demonstracao continua local demais para jurados e mentores.

## Tese

O runner competitivo continua CLI-first. A demo publica e apenas a camada de explicacao, reproducao e evidencia.

## Entregaveis

- Workflow ou runbook de GitHub Pages para publicar `demo-site/`.
- `docs/DEMO_DEPLOYMENT.md`.
- Atualizacao de `submission/final/submission-status.json`.
- Atualizacao de `submission/final-checklist.md`.
- Teste/check que valida links internos da demo.
- `scripts/check_demo_site.py`.
- Relatorio `reports/generated/demo-site-check.md`.

## Checklist

- [x] Decidir caminho de deploy: GitHub Pages via Actions ou Pages manual.
- [x] Criar `docs/DEMO_DEPLOYMENT.md`.
- [x] Criar `scripts/check_demo_site.py`.
- [x] Validar que `demo-site/index.html` referencia apenas assets publicaveis.
- [x] Validar links para `public-reports/*.md`.
- [x] Validar links para README e SUBMISSION no GitHub.
- [x] Validar ausencia de secrets, IPs privados e paths locais na demo.
- [x] Publicar URL HTTPS da demo.
- [x] Atualizar `submission/final/submission-status.json` com `demo_url`.
- [x] Atualizar `ci_status` automaticamente ou por comando documentado.
- [x] Fazer `python3 scripts/submission_readiness_check.py --strict` falhar apenas por video real, se o placeholder continuar aprovado.
- [x] Integrar check da demo ao `offline_release_check.sh` sem depender da URL externa.

## Criterios de aceite

- Existe uma URL HTTPS para a demo.
- A demo abre sem backend, login ou creditos.
- Links internos e public reports passam em check local.
- O strict readiness nao falha mais por `demo_url`.
- O deploy nao vira dependencia do evaluator tecnico.

## Metricas

- Links internos validos.
- Tamanho total publicavel de `demo-site/`.
- Numero de problemas de sanitizacao.
- Status strict antes/depois.

## Comandos esperados

```bash
python3 scripts/check_demo_site.py --check --report reports/generated/demo-site-check.md
python3 scripts/submission_readiness_check.py --strict
```

## Riscos

- Publicar a demo com links quebrados.
- Confundir demo visual com runtime competitivo.
- Marcar `ci_status=green` manualmente e esquecer de validar o commit atual.

## Decisao

O deploy deve ser estatico, barato e reversivel. Se exigir backend, auth, banco de dados ou segredo, sai do escopo.

## Definition of Done

- Demo publicada em URL HTTPS.
- Strict readiness atualizado.
- Check local da demo existe.
- Checklist final reflete estado real de submissao.
