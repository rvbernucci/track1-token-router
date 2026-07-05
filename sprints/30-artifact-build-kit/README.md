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

- [ ] Criar shotlist de video por cena.
- [ ] Criar comandos exatos que aparecem no video.
- [ ] Criar speaker notes curtas por slide.
- [ ] Gerar ou preparar `slides.pdf`.
- [ ] Gerar ou preparar cover PNG/JPG.
- [ ] Criar checklist de audio, tela, terminal e tempo.
- [ ] Criar pasta `submission/final/`.
- [ ] Criar script de build/validacao de artefatos.
- [ ] Adicionar `--strict` ao readiness check.
- [ ] Em `--strict`, exigir repo URL.
- [ ] Em `--strict`, exigir demo URL.
- [ ] Em `--strict`, exigir video MP4 ou placeholder aprovado.
- [ ] Em `--strict`, exigir slides PDF.
- [ ] Em `--strict`, exigir cover PNG/JPG.
- [ ] Em `--strict`, exigir CI verde informado.
- [ ] Documentar pendencias que so fecham no kickoff.

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
