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

- [x] Criar `prompts/versions/v1/`.
- [x] Criar `prompts/manifest.json`.
- [x] Exportar prompts atuais para arquivos `.txt`.
- [x] Criar analisador de tamanho aproximado.
- [x] Comparar prompts por versao.
- [x] Detectar prompts vazios ou ausentes.
- [x] Gerar `reports/generated/prompt-ablation.md`.
- [x] Gerar `reports/generated/prompt-ablation.json`.
- [x] Adicionar testes.
- [x] Integrar no release check offline.

## Criterios de aceite

- Prompts atuais ficam versionados fora do codigo.
- O ablation lab roda sem modelo real.
- O relatorio mostra tamanho e risco operacional de cada prompt.
- Testes garantem que o manifesto nao apodrece.

## Saida esperada

Uma base limpa para testar prompt variants quando o runtime real chegar.

## Evidencia local

```bash
python3 scripts/prompt_ablation.py --check
python3 -m unittest tests.test_prompt_ablation
scripts/offline_release_check.sh
```

## Decisao

Os prompts ficam versionados como snapshot em `prompts/versions/v1/`, mas o runtime ainda usa `router/core/prompts.py`. Isso evita mudar comportamento durante a sprint e cria uma base segura para ablation quando houver modelo real.
