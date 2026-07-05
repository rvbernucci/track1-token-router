# Sprint 13 - Prompt Versioning & Ablation Lab

## Tipo

Nao depende de credito.

## Objetivo

Versionar prompts e criar um laboratorio de ablation que compara tamanho, papeis, risco e intencao dos prompts sem precisar chamar modelos reais.

## Entregaveis

- Pasta `prompts/versions/`.
- Manifesto de prompts.
- Snapshots versionados de M1, M2A, M2B e Fireworks.
- Script `scripts/prompt_ablation.py`.
- Relatorio Markdown/JSON.
- Testes de manifesto e analise.

## Checklist

- [ ] Criar `prompts/versions/v1/`.
- [ ] Criar `prompts/manifest.json`.
- [ ] Exportar prompts atuais para arquivos `.txt`.
- [ ] Criar analisador de tamanho aproximado.
- [ ] Comparar prompts por versao.
- [ ] Detectar prompts vazios ou ausentes.
- [ ] Gerar `reports/generated/prompt-ablation.md`.
- [ ] Gerar `reports/generated/prompt-ablation.json`.
- [ ] Adicionar testes.
- [ ] Integrar no release check offline.

## Criterios de aceite

- Prompts atuais ficam versionados fora do codigo.
- O ablation lab roda sem modelo real.
- O relatorio mostra tamanho e risco operacional de cada prompt.
- Testes garantem que o manifesto nao apodrece.

## Saida esperada

Uma base limpa para testar prompt variants quando o runtime real chegar.

