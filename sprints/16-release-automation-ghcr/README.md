# Sprint 16 - Release Automation & GHCR

## Tipo

Nao depende de credito.

## Objetivo

Automatizar release, tags, release notes e publicacao opcional de imagem no GitHub Container Registry.

## Entregaveis

- Workflow de release.
- Build Docker multi-evento.
- Publicacao GHCR em tag.
- Script de release notes.
- Documentacao de tags.
- Testes/validacoes que nao exigem segredo local.

## Checklist

- [x] Criar workflow `release.yml`.
- [x] Publicar GHCR apenas em tags.
- [x] Usar `GITHUB_TOKEN`, sem segredo manual.
- [x] Criar `scripts/generate_release_notes.py`.
- [x] Documentar formato de tag.
- [x] Adicionar dry-run local de release notes.
- [x] Validar YAML/workflow em teste estatico simples.
- [x] Atualizar README.
- [x] Rodar release check offline.

## Criterios de aceite

- O workflow existe e e seguro para repo publico.
- GHCR nao depende de credito AMD/Fireworks.
- Release notes podem ser geradas localmente.
- A automacao nao publica em pushes comuns de `main`.

## Saida esperada

Um caminho reproduzivel para distribuir imagem e release quando quisermos marcar uma versao.

## Evidencia local

```bash
python3 scripts/generate_release_notes.py --tag offline-dry-run
python3 -m unittest tests.test_release_automation
scripts/offline_release_check.sh
```

## Decisao

A publicacao GHCR roda apenas em tags `v*` e `offline-*`. Push normal em `main` continua usando apenas o workflow de CI, sem publicar imagem.
