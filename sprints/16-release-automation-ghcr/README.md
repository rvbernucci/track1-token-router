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

- [ ] Criar workflow `release.yml`.
- [ ] Publicar GHCR apenas em tags.
- [ ] Usar `GITHUB_TOKEN`, sem segredo manual.
- [ ] Criar `scripts/generate_release_notes.py`.
- [ ] Documentar formato de tag.
- [ ] Adicionar dry-run local de release notes.
- [ ] Validar YAML/workflow em teste estatico simples.
- [ ] Atualizar README.
- [ ] Rodar release check offline.

## Criterios de aceite

- O workflow existe e e seguro para repo publico.
- GHCR nao depende de credito AMD/Fireworks.
- Release notes podem ser geradas localmente.
- A automacao nao publica em pushes comuns de `main`.

## Saida esperada

Um caminho reproduzivel para distribuir imagem e release quando quisermos marcar uma versao.

