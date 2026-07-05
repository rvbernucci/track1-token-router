# Sprint 30 - Artifact Build Kit

## Tipo

Nao depende de credito.

## Objetivo

Transformar os textos de submissao em artefatos finais ou semi-finais: slides PDF, cover PNG/JPG, roteiro de gravacao, checklist de video e modo estrito de readiness.

## Por que importa

A lablab avalia tambem apresentacao. Um projeto tecnicamente forte pode perder clareza se o video, slide deck, cover e demo URL forem improvisados na ultima hora.

## Tese

Artefatos finais devem ser buildaveis como codigo. O que puder ser validado por script nao deve depender de memoria humana no dia da submissao.

## Entregaveis

- `submission/final/`.
- `submission/final/slides.pdf` ou pipeline documentado para gerar.
- `submission/final/cover.png` ou `cover.jpg`.
- `submission/recording-shotlist.md`.
- `submission/final-checklist.md`.
- `scripts/build_submission_artifacts.py`.
- `scripts/submission_readiness_check.py --strict`.
- Testes para modo estrito.

## Checklist

- [x] Criar shotlist de video por cena.
- [x] Criar comandos exatos que aparecem no video.
- [x] Criar speaker notes curtas por slide.
- [x] Gerar ou preparar `slides.pdf`.
- [x] Gerar ou preparar cover PNG/JPG.
- [x] Criar checklist de audio, tela, terminal e tempo.
- [x] Criar pasta `submission/final/`.
- [x] Criar script de build/validacao de artefatos.
- [x] Adicionar `--strict` ao readiness check.
- [x] Em `--strict`, exigir repo URL.
- [x] Em `--strict`, exigir demo URL.
- [x] Em `--strict`, exigir video MP4 ou placeholder aprovado.
- [x] Em `--strict`, exigir slides PDF.
- [x] Em `--strict`, exigir cover PNG/JPG.
- [x] Em `--strict`, exigir CI verde informado.
- [x] Documentar pendencias que so fecham no kickoff.

## Criterios de aceite

- O modo normal continua passando sem artefatos finais pesados.
- O modo estrito falha enquanto URLs e arquivos finais nao existirem.
- O time sabe exatamente o que gravar em ate 5 minutos.
- Slides e cover seguem a narrativa do Track 1.

## Metricas

- Duracao estimada do video.
- Numero de slides.
- Tamanho dos arquivos finais.
- Numero de pendencias restantes no modo estrito.

## Comandos esperados

```bash
python3 scripts/build_submission_artifacts.py --check
python3 scripts/submission_readiness_check.py --strict
```

## Riscos

- Gastar tempo em design e esquecer reproducibilidade.
- Criar arquivos binarios grandes sem necessidade.
- Fazer promessas no pitch que o runner ainda nao cumpre.

## Decisao

O artifact kit deve ser pragmatico. Se um artefato ainda nao puder ser finalizado sem credito, o sprint deve deixar placeholder validado e lista exata do que falta.

## Definition of Done

- Shotlist existe.
- Modo `--strict` existe.
- Artefatos finais ou placeholders controlados existem.
- Checklist final cobre lablab, repo, video, slides, cover, demo URL e CI.

## Evidencias

- `submission/recording-shotlist.md` define cenas, tempo e comandos do video.
- `submission/final-checklist.md` cobre lablab, repo, demo, video, artefatos e kickoff.
- `scripts/build_submission_artifacts.py --check` gera `submission/final/slides.pdf`, `cover.png`, `speaker-notes.md`, `artifact-manifest.json`, `README.md` e placeholder de video.
- `scripts/submission_readiness_check.py --strict` exige repo URL, demo URL, CI verde, slides PDF, cover PNG/JPG e video ou placeholder aprovado.
- `tests/test_submission_readiness.py` cobre builder, strict pendente e strict aprovado em fixture temporaria.
- Estado atual esperado do strict: falha somente por `demo_url` ausente e `ci_status` ainda nao marcado como `green`.
