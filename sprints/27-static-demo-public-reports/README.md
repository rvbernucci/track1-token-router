# Sprint 27 - Static Demo And Public Reports

## Tipo

Nao depende de credito.

## Objetivo

Criar uma demo estatica publicavel e um fluxo de exportacao de reports publicos para explicar o projeto rapidamente sem depender de AMD Developer Cloud, Fireworks, Native.Builder ou servidor proprio.

## Por que importa

A documentacao da lablab exige prototipo acessivel por URL. Mesmo que o core seja CLI-first, a submissao precisa ser entendida por jurados, mentores e avaliadores humanos em poucos minutos.

O objetivo nao e construir uma UI complexa. E criar uma vitrine estatica, segura e fiel ao runner competitivo.

## Tese

O demo site deve responder quatro perguntas:

- o que o router faz;
- por que isso economiza tokens remotos;
- como reproduzir localmente;
- quais evidencias offline provam readiness.

## Entregaveis

- `demo-site/`.
- `demo-site/index.html`.
- `demo-site/assets/` quando necessario.
- `scripts/export_public_report.py`.
- `reports/public/`.
- `reports/public/battle-report.md`.
- `reports/public/fuzz-report.md`.
- `reports/public/submission-readiness.md`.
- `docs/PUBLIC_DEMO_RUNBOOK.md`.
- Atualizacao em `submission/demo-plan.md`.
- Testes para exportacao sem segredos.

## Checklist

- [ ] Criar estrutura `demo-site/`.
- [ ] Criar HTML estatico sem dependencia de build tool.
- [ ] Incluir pitch em 90 segundos.
- [ ] Incluir diagrama do fluxo competitivo.
- [ ] Incluir exemplo `solver_arithmetic` com zero tokens remotos.
- [ ] Incluir exemplo de remote audit dry-run.
- [ ] Incluir links para README, SUBMISSION e reports publicos.
- [ ] Criar `scripts/export_public_report.py`.
- [ ] Exportar battle report publico.
- [ ] Exportar fuzz report publico.
- [ ] Exportar submission readiness publico.
- [ ] Redigir prompts longos antes de publicar.
- [ ] Mascarar paths locais absolutos.
- [ ] Bloquear IPs privados, hostnames privados e tokens.
- [ ] Criar teste que injeta segredo sintetico e espera bloqueio.
- [ ] Criar comando local para servir demo com `python3 -m http.server`.
- [ ] Criar checklist de GitHub Pages.
- [ ] Integrar export publico ao release check ou a um check dedicado.

## Criterios de aceite

- `demo-site/index.html` abre localmente sem instalar dependencias.
- `python3 scripts/export_public_report.py --check` passa sem segredos.
- `reports/public/` contem apenas artefatos seguros para compartilhar.
- O demo site explica a arquitetura sem exigir leitura do codigo.
- O demo nao vira dependencia do evaluator tecnico.

## Metricas

- Tempo para entender a tese: alvo menor que 90 segundos.
- Numero de reports publicos exportados: minimo 3.
- Secret scan em reports publicos: zero achados.
- Comando de reproducao local visivel no primeiro scroll.

## Comandos esperados

```bash
python3 scripts/export_public_report.py --check
cd demo-site
python3 -m http.server 8080
```

## Riscos

- Criar uma landing page bonita mas desconectada do runner real.
- Publicar logs ou prompts que nao deveriam sair do repo.
- Gastar tempo demais em visual antes de fechar o conteudo tecnico.

## Decisao

O demo deve ser estatico, pequeno e auditavel. Se uma melhoria exigir backend, auth, banco de dados ou deploy complexo, ela fica fora deste sprint.

## Definition of Done

- Demo estatica existe.
- Reports publicos sao exportados por script.
- Secret scan cobre os artefatos compartilhaveis.
- Submission demo checklist aponta para o novo fluxo.
- Documentacao explica como publicar no GitHub Pages ou equivalente.
