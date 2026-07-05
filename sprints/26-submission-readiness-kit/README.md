# Sprint 26 - Submission Readiness Kit

## Tipo

Nao depende de credito.

## Objetivo

Preparar o pacote de submissao do hackathon antes dos creditos: descricoes, tags, roteiro de video, estrutura de slides, cover, demo URL, checklist de arquivos e readiness check automatizado.

## Por que importa

Mesmo um runner forte pode perder se a submissao estiver incompleta, confusa ou dificil de reproduzir. A plataforma lablab exige artefatos alem do codigo.

## Entregaveis

- `submission/`.
- `submission/short-description.md`.
- `submission/long-description.md`.
- `submission/tags.md`.
- `submission/video-script.md`.
- `submission/slides-outline.md`.
- `submission/demo-plan.md`.
- `submission/cover-brief.md`.
- Script `scripts/submission_readiness_check.py`.
- Relatorio `reports/generated/submission-readiness.md`.
- Atualizacao de `SUBMISSION.md`.

## Checklist

- [x] Escrever short description ate 255 caracteres.
- [x] Escrever long description com mais de 100 palavras.
- [x] Definir project title final.
- [x] Definir technology/category tags.
- [x] Criar roteiro de video ate 5 minutos.
- [x] Criar estrutura de slides PDF.
- [x] Criar plano de demo em CLI.
- [x] Criar plano de demo visual opcional.
- [x] Criar brief de cover image PNG/JPG.
- [x] Criar checklist de URL de demo.
- [x] Criar checklist de repo publico.
- [x] Criar checklist de Docker/CI.
- [x] Criar readiness script.
- [x] Validar campos obrigatorios da lablab.
- [x] Integrar readiness ao battle drill ou release check.
- [x] Documentar o que fica pendente ate kickoff.

## Criterios de aceite

- A submissao tem todos os textos base prontos.
- O readiness check falha quando artefato obrigatorio falta.
- O README aponta claramente como rodar e avaliar.
- O time consegue gravar video e montar slides sem reinventar narrativa.

## Saida esperada

Um pacote de submissao quase pronto, esperando apenas detalhes reais do kickoff e URLs finais.

## Decisao

O kit deve vender o projeto como runner competitivo, nao como plataforma generica. A narrativa principal e accuracy com menor token remoto por meio de orquestracao calibrada.

## Evidencia de fechamento

- `python3 scripts/submission_readiness_check.py`: `ok=true`, short description com 199 caracteres, long description com 162 palavras, 12 tags e 10 slides.
- `python3 -m unittest tests.test_submission_readiness`: readiness positivo, CLI e falha por artefato ausente testados.
- `scripts/offline_release_check.sh`: readiness integrado a porteira pesada.
- Pendencias ate kickoff documentadas como warnings: URL publica, video/demo URL e benchmark real AMD/Fireworks.
