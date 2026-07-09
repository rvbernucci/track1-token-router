# Fireworks Capability Study

Atualizado em: 2026-07-09

Fonte principal: [`https://docs.fireworks.ai/llms.txt`](https://docs.fireworks.ai/llms.txt)

Mapa completo gerado em: [`docs/FIREWORKS_DOCS_MAP.md`](./FIREWORKS_DOCS_MAP.md)

## Objetivo

Entender o que a Fireworks oferece antes de gastar credito ou adicionar complexidade ao Track 1.

Perguntas que este estudo precisa responder:

- quais superficies Fireworks podem aparecer no scoring oficial;
- quais features reduzem tokens sem reduzir accuracy;
- quais features so ajudam produto/operacao, mas nao o hackathon;
- onde fine-tuning e permitido de forma segura;
- onde deployment/LoRA pode quebrar compatibilidade com `ALLOWED_MODELS`;
- quais docs precisam virar teste, script ou env profile no repo.

## Mapa de capacidades

| Area | O que Fireworks faz | Relevancia Track 1 |
|---|---|---|
| Serverless inference | Chat/completions/responses em endpoint OpenAI-compatible, serving paths, pricing, rate limits e prompt caching. | Critica. E o caminho pontuado quando usamos `FIREWORKS_BASE_URL`. |
| Model library | Modelos serverless, modelos custom, quantizacao e familias como Kimi. | Critica. Precisamos escolher o menor modelo suficiente. |
| API reference | Chat completions, completions, responses, evaluators, quotas, secrets, rerank. | Alta. Define parametros, formatos e endpoints. |
| Guides | Text models, reasoning, tool calling, batch, predicted outputs, embeddings/reranking, error codes. | Alta. Pode reduzir tokens ou falhas de formato. |
| Structured outputs | JSON schema/custom grammar. | Alta se o harness aceitar parametros; pode reduzir retries por JSON invalido. |
| Fine-tuning | SFT, RFT, DPO/ORPO, evaluators, LoRA, managed fine-tuning. | Media. Fine-tunar roteador e seguro; LoRA respondedor depende do harness. |
| Dedicated deployments | On-demand deployments, autoscaling, routers, benchmarking, speculative decoding. | Media/baixa para Track 1. Usar so se `ALLOWED_MODELS` incluir deployment IDs. |
| Batch API | Jobs assincronos e desconto para processamento em lote. | Baixa para scoring; util para calibracao offline. |
| SDK/tools | Python, TypeScript, Go, Rust, OpenAI/Anthropic compatibility, firectl. | Media. Ajuda integracao, mas Docker final deve ficar simples. |
| Accounts/billing | Service accounts, usage export, quotas, billing. | Operacional. Ajuda controlar credito. |
| Ecosystem | FireConnect, IDEs, BYOC, Azure Foundry, observability. | Baixa para Track 1; bom para produto depois. |

## Ordem de estudo recomendada

1. [`getting-started/introduction.md`](https://docs.fireworks.ai/getting-started/introduction.md) para a visao geral.
2. [`getting-started/quickstart.md`](https://docs.fireworks.ai/getting-started/quickstart.md) para chamada serverless minima.
3. [`serverless/overview.md`](https://docs.fireworks.ai/serverless/overview.md) para billing, headers, prompt caching e quando usar Serverless.
4. [`serverless/pricing.md`](https://docs.fireworks.ai/serverless/pricing.md) para custo por modelo.
5. [`serverless/serving-paths.md`](https://docs.fireworks.ai/serverless/serving-paths.md) para Standard/Priority/Fast.
6. [`guides/querying-text-models.md`](https://docs.fireworks.ai/guides/querying-text-models.md) para parametros de texto.
7. [`guides/reasoning.md`](https://docs.fireworks.ai/guides/reasoning.md) para controlar raciocinio e evitar tokens escondidos.
8. [`structured-responses/structured-response-formatting.md`](https://docs.fireworks.ai/structured-responses/structured-response-formatting.md) para formatos estritos.
9. [`guides/inference-error-codes.md`](https://docs.fireworks.ai/guides/inference-error-codes.md) para fallback robusto.
10. [`fine-tuning/managed-finetuning-intro.md`](https://docs.fireworks.ai/fine-tuning/managed-finetuning-intro.md) e [`fine-tuning/deploying-loras.md`](https://docs.fireworks.ai/fine-tuning/deploying-loras.md) para limites de LoRA.

## Hipoteses de vantagem para testar

### 1. Prompt caching

Possivel vantagem: system prompt fixo e payload variavel pequeno podem reduzir custo/latencia em chamadas repetidas.

Teste local:

- manter system prompt estatico;
- medir tokens/custo com e sem prefixo fixo;
- registrar headers se Fireworks expuser cache hit/miss.

### 2. Reasoning controls

Possivel vantagem: alguns modelos gastam tokens em raciocinio. Controlar `reasoning_effort` pode reduzir custo.

Ja temos evidência local em `docs/RUNBOOK_FIREWORKS.md`: `reasoning_effort=none/low` melhora custo em alguns modelos, mas pode quebrar modelos fortes se for aplicado globalmente.

### 3. Structured outputs

Possivel vantagem: forçar JSON schema/custom grammar pode reduzir retries e respostas com markdown.

Risco:

- se o parametro nao for aceito por todos os modelos permitidos, precisa fallback sem extra body;
- pode aumentar input tokens.

### 4. Fine-tuned router

Possivel vantagem: treinar um classificador pequeno/local para prever rota (`solver`, `cheap`, `strong`, `abstain`) com base nos microbenches.

Seguro porque:

- nao muda modelo respondedor;
- nao precisa chamar Fireworks;
- reduz risco de over-routing para modelo caro.

### 5. LoRA responder

Possivel vantagem: modelo pequeno com melhor format-following.

Risco alto:

- Fireworks LoRA exige deployment on-demand/dedicado;
- o ID pode ficar fora de `ALLOWED_MODELS`;
- tokens Fireworks continuam contando;
- overhead de LoRA nao mergeado pode piorar latencia/throughput.

Decisao atual: estudar, mas nao usar no runtime principal.

### 6. Batch API

Possivel vantagem: calibracao barata fora do scoring.

Risco:

- nao serve para contrato sincrono `/input/tasks.json -> /output/results.json`;
- nao deve entrar no container final.

## O que vira acao no repo

- manter `scripts/map_fireworks_docs.py` para atualizar o mapa quando a doc mudar;
- usar `docs/FIREWORKS_DOCS_MAP.md` como inventario completo;
- transformar docs criticas em experimentos pequenos antes de gastar credito;
- nao misturar features de produto com caminho final do hackathon;
- manter submissao final serverless/local-compatible e `ALLOWED_MODELS`-first.

## Proxima rodada de estudo

Prioridade 1:

- Serverless overview/pricing/serving paths/rate limits;
- text models/reasoning/structured outputs/error codes;
- model library e modelos permitidos Track 1.

Prioridade 2:

- fine-tuning do roteador;
- evaluators e datasets;
- prompt caching e predicted outputs.

Prioridade 3:

- deployments/routers/speculative decoding;
- batch API;
- SDKs/ecosystem.
