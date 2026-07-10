# Runbook Native.Builder

## Objetivo

Usar Native.Builder/NativelyAI como ferramenta auxiliar de demo, documentacao ou apresentacao, nao como runtime competitivo do Track 1.

## Papel correto

- Criar demo visual do fluxo do router.
- Gerar documentacao navegavel para jurados.
- Ajudar pitch/video.
- Nao substituir CLI, eval harness ou scoring path.

## Entradas seguras

- Descricao publica da arquitetura.
- Screenshots sem segredo.
- Reports gerados sem prompts sensiveis.
- Diagramas Mermaid ou Markdown.

## Entradas proibidas

- API keys.
- IP privado da VM.
- Logs com prompts sensiveis.
- Dados de avaliacao oficial se houver regra de confidencialidade.

## Fluxo sugerido

1. Exportar `SUBMISSION.md`, `docs/DETERMINISTIC_SOLVERS.md` e report do battle drill.
2. Criar demo auxiliar explicando:
   - FunctionGemma assessment;
   - regression and minimax decision engine;
   - deterministic solver route;
   - Gemma 4 E2B text-only route;
   - Fireworks Pareto fallback.
3. Usar a demo apenas como material de apresentacao.
4. Manter a execucao real no CLI.

## Health check de posicionamento

Se uma mudanca em Native.Builder for necessaria para o score tecnico, estamos no caminho errado.

O core competitivo deve continuar reproduzivel por:

```bash
scripts/offline_release_check.sh
```
