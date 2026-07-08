# Model Capability Research For Pareto Routing

## Objetivo

Este documento transforma paginas oficiais, model cards e technical reports em criterios praticos de roteamento para o Track 1.

O Pareto final nao deve ser apenas `menor preco`. Ele deve combinar:

- custo estimado de input/output;
- capacidade comprovada por dominio;
- risco de overthinking e tokens de raciocinio;
- suporte a chat/completions;
- suporte a tool/function calling quando relevante;
- confianca da evidencia: paper/model card > official launch note > provider listing > benchmark interno sem metodologia aberta.

## Regra De Ouro

O roteador deve primeiro perguntar: "qual e o menor modelo suficientemente bom para este dominio?".

Se a tarefa for simples, custo vence. Se a tarefa for forte, o modelo precisa passar um piso de capacidade antes de competir por custo. Se a tarefa depende de ferramenta auxiliar, embedding/reranker so entram se houver RAG/ranking real; nunca devem produzir resposta final.

## Mapa Executivo

| Familia / modelos Fireworks | Melhor uso no Pareto | Sinal de entrada | Cuidado |
| --- | --- | --- | --- |
| `gpt-oss-20b` | classificacao, formato curto, respostas simples | label, sentiment, JSON simples, resposta curta | maior risco de alucinacao/factualidade que modelos maiores |
| `gpt-oss-120b` | raciocinio geral barato, tool use, structured output | logic, math, general hard, precisa bom custo | `reasoning_effort=low/medium`; `none` pode ser rejeitado |
| `deepseek-v4-flash` | general/medium barato, raciocinio com budget, resumo | perguntas medias, linguagem geral, simples agentic | nao tratar como Pro em conhecimento profundo ou agente muito complexo |
| `deepseek-v4-pro` | raciocinio/codigo/knowledge de alta confianca | STEM dificil, codigo dificil, knowledge dificil | caro e lento; usar quando custo menor falha ou tarefa exige high confidence |
| `kimi-k2p7-code` | codigo long-horizon e agentic coding | escrever/debugar/refatorar codigo, multi-step tool calls | sempre thinking; pode gastar tokens de saida se nao controlarmos output |
| `kimi-k2p6` | fallback Kimi para codigo/agente | codigo forte se K2.7 nao estiver liberado | K2.7 melhora token efficiency e benchmarks |
| `minimax-m3` | melhor candidato custo/capacidade para codigo/agente no catalogo atual | coding, bugfix, terminal, agent, multimodal | benchmarks oficiais/fornecedor; validar no nosso eval |
| `minimax-m2p7` | fallback barato para agente/produtividade/codigo | office, tool-use, code, SRE-style tasks | inferior ao M3 em contexto/multimodalidade |
| `qwen3p7-plus` | modelo equilibrado multimodal/tool/coding | multimodal, GUI, tool use, multilingual | pouca transparencia especifica do Plus; usar Qwen3/Qwen3.7 como proxy |
| `glm-5p2` | long-horizon coding, repo-scale context, engineering constraints | repos grandes, refatoracao longa, 1M context | mais caro que M3/Qwen/DeepSeek Flash |
| `glm-5p1` | long-horizon engineering fallback | agente/codigo quando 5.2 indisponivel | 5.2 supera 5.1 em coding e contexto |
| `nemotron-3-ultra-nvfp4` | agentic reasoning, math/code/science com throughput | tarefas longas, planning, tool calling, 1M context | preco medio; pode ser forte demais para cheap/medium |
| `qwen3-embedding-8b` | embedding para RAG/search | precisa buscar contexto em corpus | nao e modelo de resposta final |
| `qwen3-reranker-8b` | reranking para RAG/search | existe lista de documentos candidata | nao e modelo de resposta final |

## Evidencia Por Familia

### OpenAI gpt-oss-20b / gpt-oss-120b

Fontes principais:

- [OpenAI gpt-oss model card](https://openai.com/index/gpt-oss-model-card/)
- [OpenAI introducing gpt-oss](https://openai.com/index/introducing-gpt-oss/)
- [OpenAI gpt-oss GitHub](https://github.com/openai/gpt-oss)
- [gpt-oss arXiv model card](https://arxiv.org/html/2508.10925v1)

Treinamento e arquitetura:

- modelos open-weight text-only, Apache 2.0;
- MoE Transformer;
- `gpt-oss-120b`: 117B parametros totais, 5.1B ativos/token, 128k context;
- `gpt-oss-20b`: 21B parametros totais, 3.6B ativos/token, 128k context;
- dataset text-only com foco em STEM, coding e conhecimento geral;
- post-training com SFT e high-compute RL para reasoning e tool use;
- tokenizer `o200k_harmony`; usar Harmony/chat template correto importa.

Onde performa melhor:

- `gpt-oss-120b`: reasoning geral, math, tool use, structured outputs, function calling;
- `gpt-oss-20b`: tarefas simples e especializadas com baixa latencia/custo;
- OpenAI reporta `gpt-oss-120b` proximo de `o4-mini` em benchmarks centrais e `gpt-oss-20b` comparavel a `o3-mini` em benchmarks comuns.

Riscos para Pareto:

- OpenAI reporta pior desempenho que `o4-mini` em SimpleQA/PersonQA; isso sinaliza risco em factualidade sem busca;
- instruction hierarchy e prompt-injection sao mais fracos que `o4-mini`;
- para Track 1, `gpt-oss-20b` deve ser cheap-first; `gpt-oss-120b` deve ser reasoning-budget-first.

Decisao de roteamento:

- `gpt-oss-20b`: cheap/default para classificacao e formatacao simples.
- `gpt-oss-120b`: medium/strong quando o dominio e logic/math/general e o custo precisa ficar baixo.
- Evitar para pergunta factual atual sem ferramenta externa; se usar, exigir resposta curta e incerteza explicita.

### DeepSeek V4 Flash / DeepSeek V4 Pro

Fontes principais:

- [DeepSeek V4 Preview Release](https://api-docs.deepseek.com/news/news260424)
- [DeepSeek-V4-Pro Hugging Face model card](https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro)
- [DeepSeek-V4-Pro NVIDIA NIM model card](https://build.nvidia.com/deepseek-ai/deepseek-v4-pro/modelcard)

Treinamento e arquitetura:

- MoE com 1M context;
- `DeepSeek-V4-Pro`: 1.6T parametros totais, 49B ativos;
- `DeepSeek-V4-Flash`: 284B parametros totais, 13B ativos;
- hybrid attention com CSA + HCA para reduzir custo de contexto longo;
- mHC para estabilidade de sinal;
- Muon optimizer;
- pretraining em mais de 32T tokens segundo o model card HF;
- post-training em duas etapas: especialistas por dominio com SFT + GRPO, depois consolidacao via on-policy distillation;
- modos `Non-think`, `Think High`, `Think Max`.

Onde performa melhor:

- Pro: math/STEM/coding, world knowledge, agente complexo, long context;
- Flash: raciocinio proximo do Pro quando recebe thinking budget, bom para tarefas agentic simples, mais rapido e economico;
- benchmark oficial mostra Pro Max forte em LiveCodeBench, Codeforces, GPQA Diamond, HMMT, IMOAnswerBench, Terminal Bench, SWE Verified/Pro, BrowseComp e Toolathlon.

Riscos para Pareto:

- Flash nao deve herdar automaticamente o mesmo piso do Pro para conhecimento profundo e agente complexo;
- Pro pode dominar por qualidade, mas e caro/lento;
- modos de thinking podem explodir tokens se nao houver limite de saida.

Decisao de roteamento:

- `deepseek-v4-flash`: medium-general e reasoning barato quando `gpt-oss-120b` nao for suficiente ou quando houver bom custo/latencia.
- `deepseek-v4-pro`: strong fallback para math/coding/agent/knowledge quando falhar modelo barato ou quando input sinalizar alta complexidade.

### Moonshot Kimi K2.7 Code / Kimi K2.6

Fontes principais:

- [Kimi K2.7 Code official docs](https://platform.kimi.ai/docs/guide/kimi-k2-7-code-quickstart)
- [Kimi K2.7 Code Hugging Face model card](https://huggingface.co/moonshotai/Kimi-K2.7-Code)
- [Kimi K2 GitHub](https://github.com/moonshotai/kimi-k2)
- [Moonshot AI homepage](https://www.moonshot.ai/)

Treinamento e arquitetura:

- K2 family: MoE, 1T total, 32B active, Muon optimizer lineage;
- Kimi K2 base was pre-trained on 15.5T tokens according to the Kimi K2 repository;
- K2.7 Code is built on K2.6 and optimized for coding-focused agentic work;
- K2.7 Code: 1T total, 32B active, 256K context, MLA attention, MoonViT vision encoder;
- supports image/video input in official API;
- K2.7 Code does not support non-thinking mode.

Onde performa melhor:

- long-horizon coding;
- instruction compliance in long contexts;
- multi-step tool invocation;
- agentic coding workflows;
- Kimi reports K2.7 Code improves over K2.6 in coding and agentic benchmarks and reduces overthinking tendencies by around 30%.

Benchmarks destacados:

- Kimi Code Bench v2: K2.6 50.9, K2.7 Code 62.0;
- Program Bench: K2.6 48.3, K2.7 Code 53.6;
- MCP Atlas: K2.6 69.4, K2.7 Code 76.0;
- MCP Mark Verified: K2.6 72.8, K2.7 Code 81.1.

Riscos para Pareto:

- sempre thinking significa risco de output tokens;
- para tarefas triviais, e desperdicio;
- para Track 1, precisa prompt de resposta final curta se chamado.

Decisao de roteamento:

- `kimi-k2p7-code`: codigo forte, debug, agentic coding, long-horizon code, multimodal tool tasks.
- `kimi-k2p6`: fallback se K2.7 Code nao estiver em `ALLOWED_MODELS`.
- Evitar em classificacao/formato curto.

### Z.ai GLM-5.2 / GLM-5.1

Fontes principais:

- [GLM-5.2 official docs](https://docs.z.ai/guides/llm/glm-5.2)
- [GLM-5.1 official docs](https://docs.z.ai/guides/llm/glm-5.1)
- [GLM 5.2 Fireworks model page](https://fireworks.ai/models/fireworks/glm-5p2)
- [GLM 5.1 Fireworks model page](https://fireworks.ai/models/fireworks/glm-5p1)

Treinamento e arquitetura:

- GLM-5.2: flagship foundation model, text-in/text-out, 1M context, 128K max output;
- GLM-5.1: flagship model for long-horizon tasks, 200K context, 128K max output;
- Fireworks lists GLM-5.2 as 743B MoE and GLM-5.1 as 754B-parameter MoE;
- Z.ai discloses specialized training for long-horizon coding and engineering workflows, but not a full data recipe in the docs we found.

Onde performa melhor:

- long-horizon engineering;
- repo-scale codebase understanding;
- refactoring with constraints;
- mobile/on-device debugging loops;
- production-grade standard adherence;
- code-to-video / engineering artifacts.

Benchmarks destacados:

- GLM-5.2 docs report Terminal-Bench 2.1: 81.0 and SWE-bench Pro: 62.1;
- GLM-5.1 docs report SWE-Bench Pro: 58.4 and broad agent/coding/tool/browsing strength.

Riscos para Pareto:

- preco de output e maior que M3, Qwen e gpt-oss;
- pode ser excelente em hard long-horizon, mas nao deve entrar em cheap;
- 5.2 parece substituir 5.1 para tarefas de codigo/contexto longo.

Decisao de roteamento:

- `glm-5p2`: strong-long-context, repo-scale, engenharia com restricoes, tarefas onde contexto completo vale o custo.
- `glm-5p1`: fallback se 5.2 nao estiver liberado.
- Evitar em tarefas curtas, classificacao e JSON simples.

### MiniMax M3 / MiniMax M2.7

Fontes principais:

- [MiniMax M3 official blog](https://www.minimax.io/blog/minimax-m3)
- [MiniMax M3 Hugging Face model card](https://huggingface.co/MiniMaxAI/MiniMax-M3)
- [MiniMax M3 NVIDIA NIM model card](https://build.nvidia.com/minimaxai/minimax-m3/modelcard)
- [MiniMax M2.7 GitHub](https://github.com/MiniMax-AI/MiniMax-M2.7)
- [MiniMax M2.7 NVIDIA NIM model card](https://build.nvidia.com/minimaxai/minimax-m2.7/modelcard)

Treinamento e arquitetura:

- M3: multimodal MoE, around 428B total, around 22-23B active, 1M context;
- M3 uses MiniMax Sparse Attention (MSA) to scale 1M context efficiently;
- M3 undergoes mixed-modality training from the first step and uses interleaved multimodal data;
- M3 supports thinking `enabled`, `adaptive`, and `disabled`;
- M2.7: MoE, around 230B total, 10B active, 204,800 context;
- M2.7 training data is not fully disclosed, but MiniMax reports self-evolution loops and RL experiment scaffolds.

Onde performa melhor:

- M3: coding, agentic work, long-context, multimodal, video/image understanding, desktop/computer operation;
- M2.7: complex software engineering, production troubleshooting, office productivity, document editing, agent teams, tool use.

Benchmarks destacados:

- M3 official blog: SWE-Bench Pro 59.0, Terminal-Bench 2.1 66.0, SWE-fficiency 34.8, KernelBench Hard 28.8, MCP Atlas 74.2;
- M2.7 GitHub/NIM: SWE-Pro 56.22, VIBE-Pro 55.6, Terminal Bench 2 57.0, NL2Repo 39.8, GDPval-AA 1495 ELO, Toolathon 46.3, MM Claw 62.7, MLE Bench Lite 66.6% medal rate.

Riscos para Pareto:

- M3/M2.7 benchmarks sao majoritariamente reportados pelo fornecedor ou por provider model cards; precisamos validar no nosso eval;
- M3 e excelente candidato porque combina preco baixo com capacidade alta, mas o roteador nao deve assumir que sempre vence DeepSeek/Kimi/GLM em todo codigo.

Decisao de roteamento:

- `minimax-m3`: default strong-code/agentic se `ALLOWED_MODELS` incluir e o input nao exigir conhecimento profundo mais bem coberto por DeepSeek Pro.
- `minimax-m2p7`: fallback barato para code/agent/productivity se M3 nao estiver liberado.
- M3 com `thinking=disabled/adaptive` e promps curtos pode ser uma vantagem de tokens.

### Qwen3.7 Plus / Qwen3 Embedding / Qwen3 Reranker

Fontes principais:

- [Qwen3.7 official blog](https://qwen.ai/blog?id=qwen3.7)
- [Qwen3 technical report](https://arxiv.org/html/2505.09388v1)
- [Qwen docs](https://qwen.readthedocs.io/)
- [Qwen3 Embedding paper](https://arxiv.org/html/2506.05176v1)
- [Qwen3 Embedding GitHub](https://github.com/QwenLM/Qwen3-Embedding)
- [Qwen3.7 Plus Fireworks model page](https://fireworks.ai/models/fireworks/qwen3p7-plus)
- [Qwen3 Embedding 8B Fireworks model page](https://fireworks.ai/models/fireworks/qwen3-embedding-8b)
- [Qwen3 Reranker 8B Fireworks model page](https://fireworks.ai/models/fireworks/qwen3-reranker-8b)

Treinamento e arquitetura:

- Qwen3 family includes dense and MoE models from 0.6B to 235B;
- Qwen3 technical report describes unified thinking/non-thinking modes and thinking budget;
- Qwen3 expands multilingual coverage to 119 languages/dialects;
- Qwen3.7 Plus is listed by Fireworks as a serverless customized Qwen model with function calling and image input;
- Qwen3 Embedding/Reranker are built from Qwen3 foundation models and trained through multi-stage unsupervised pre-training + supervised fine-tuning with synthetic data generation/merging.

Onde performa melhor:

- Qwen3 family: multilingual, math, coding, general reasoning, agent/tool tasks;
- Qwen3.7 Plus: likely cost-effective multimodal/tool/general model when image input matters;
- Qwen3 Embedding 8B: multilingual embedding, code retrieval, cross-lingual retrieval;
- Qwen3 Reranker 8B: ranking/retrieval relevance after candidate retrieval.

Benchmarks destacados:

- Qwen3 technical report: Qwen3 models improve coding/math/general/multilingual baselines; Qwen3-32B improves EvalPlus/MultiPL-E/MBPP/CRUX-O vs comparable models;
- Qwen3 Embedding paper: Qwen3-8B-Embedding scores 70.58 on MTEB Multilingual and 80.68 on MTEB Code, with strong reranking results.

Riscos para Pareto:

- Qwen3.7 Plus specific training recipe is less transparent than open Qwen3 papers;
- embedding/reranker burn Fireworks tokens but do not answer the user;
- for Track 1, auxiliary retrieval only makes sense if the benchmark task includes documents/corpus where retrieval improves accuracy enough to pay for itself.

Decisao de roteamento:

- `qwen3p7-plus`: medium/strong general, multimodal, function-calling, multilingual, when price/capability beats GLM/Kimi/DeepSeek.
- `qwen3-embedding-8b`: never answer final; only future RAG.
- `qwen3-reranker-8b`: never answer final; only future reranking.

### NVIDIA Nemotron 3 Ultra NVFP4

Fontes principais:

- [NVIDIA Nemotron 3 Ultra NIM model card](https://build.nvidia.com/nvidia/nemotron-3-ultra-550b-a55b/modelcard)
- [Nemotron 3 Ultra arXiv](https://arxiv.org/abs/2606.15007)
- [NVIDIA Nemotron 3 Ultra research page](https://research.nvidia.com/labs/nemotron/Nemotron-3-Ultra/)

Treinamento e arquitetura:

- 550B total, 55B active;
- hybrid Mamba-Transformer MoE with LatentMoE;
- 1M context;
- NVFP4 pre-training recipe;
- around 20T text tokens;
- SFT, RL, Multi-teacher On-Policy Distillation;
- multi-environment RLVR across math, code, science, instruction following, tool use, multi-turn conversation and structured output;
- training data disclosed more extensively than most providers.

Onde performa melhor:

- long-running autonomous agentic tasks;
- planning, tool calling, math, code, science;
- high-throughput inference relative to similarly capable public models;
- cases where open model transparency/data disclosure matters.

Benchmarks/claims destacados:

- NVIDIA reports around 5x to 6x throughput advantage versus comparable open models while maintaining frontier-class accuracy;
- model card emphasizes agentic reasoning, code/math/science, long-context analysis and complex multi-step agents.

Riscos para Pareto:

- stronger than needed for cheap/medium tasks;
- may be expensive relative to gpt-oss/deepseek-flash/minimax;
- route only when strong reasoning/agentic confidence is required.

Decisao de roteamento:

- `nemotron-3-ultra-nvfp4`: strong fallback for complex agentic reasoning, math/code/science, tool calling, long context.
- Do not use for short classification/format tasks.

## Proposta De Tiers Para O Router

### Cheap

Objetivo: gastar o minimo em tarefas quase deterministicas ou linguagem curta.

Modelos preferidos:

- `gpt-oss-20b`
- `deepseek-v4-flash` se `gpt-oss-20b` falhar/nao estiver liberado
- `gpt-oss-120b` se a tarefa simples exigir um pouco mais de reasoning e ainda for barata

Evitar:

- Kimi, GLM, DeepSeek Pro, Nemotron, M3 para tarefas triviais.

### Medium

Objetivo: manter boa qualidade sem acionar modelo caro.

Modelos preferidos:

- `gpt-oss-120b`
- `deepseek-v4-flash`
- `qwen3p7-plus`
- `minimax-m3` se a tarefa tiver codigo/agente leve

Sinais:

- explicacao geral;
- resumo;
- extracao;
- pergunta factual estavel;
- multi-turn curto;
- multilingual.

### Strong Code / Agent

Objetivo: acertar tarefas onde uma resposta errada derruba accuracy.

Modelos preferidos:

- `minimax-m3` para melhor custo/capacidade inicial;
- `kimi-k2p7-code` quando codigo long-horizon e confianca importam;
- `glm-5p2` quando 1M contexto/repo-scale e essencial;
- `deepseek-v4-pro` quando coding + reasoning + knowledge exigem alta confianca;
- `nemotron-3-ultra-nvfp4` quando agente/tool/planning longo e throughput importam.

### Strong Math / Reasoning / STEM

Modelos preferidos:

- `gpt-oss-120b` se custo for prioridade;
- `deepseek-v4-pro` se a tarefa parecer olimpiada/STEM/coding competitiva;
- `nemotron-3-ultra-nvfp4` para math/science/tool reasoning;
- `qwen3p7-plus` como meio termo se permitido.

### Long Context

Modelos preferidos:

- `glm-5p2`: 1M context e foco em long-horizon engineering;
- `deepseek-v4-pro` / `deepseek-v4-flash`: 1M context com CSA/HCA;
- `minimax-m3`: 1M context com MSA e multimodal;
- `nemotron-3-ultra-nvfp4`: 1M context e agentic reasoning.

### RAG / Retrieval

Modelos auxiliares:

- `qwen3-embedding-8b`: embedding;
- `qwen3-reranker-8b`: reranking.

Regra: so usar se houver um corpus externo/documentos candidatos. Se o input for apenas uma pergunta aberta, embedding/reranker provavelmente queima token sem aumentar accuracy.

## Mudancas Sugeridas No Pareto

1. Adicionar `capability_by_domain`, nao apenas `strengths`.
2. Separar `strong_code`, `strong_math`, `long_context`, `agentic_tool`, `multimodal`, `factual`.
3. Adicionar `thinking_token_risk`: low, medium, high.
4. Adicionar `evidence_confidence`: official-paper, official-doc, provider-card, internal-benchmark.
5. Adicionar `mode_policy`: non-thinking, low, medium, high, adaptive, forced-thinking.
6. Manter embedding/reranker fora da resposta final.
7. Rodar microbench pequeno por dominio quando os creditos permitirem, porque benchmarks de fornecedor nao substituem o scoring do hackathon.

## Hipoteses Competitivas

- Para cheap tasks, `gpt-oss-20b` tende a ser o campeao se o output for rigidamente curto.
- Para reasoning barato, `gpt-oss-120b` pode ser a melhor relacao accuracy/custo, mas precisa cuidado com hallucination.
- Para codigo, `minimax-m3` e candidato numero 1 por preco/capacidade; Kimi K2.7 Code e GLM-5.2 podem vencer em codigo long-horizon, mas custam mais tokens.
- Para math/STEM dificil, DeepSeek Pro e Nemotron devem entrar como fallback de alta confianca.
- Para multimodal/GUI/video, Qwen3.7 Plus, Kimi K2.7 Code e MiniMax M3 sao os candidatos mais relevantes, mas isso so importa se o Track 1 realmente trouxer input multimodal.
- Para long context, usar 1M-context models apenas se o input passar de um limite de tamanho ou contiver corpus/projeto; caso contrario, e desperdicio de custo.

## Proximo Passo

Criar um micro-eval local com 5 a 10 prompts por dominio:

- cheap classification;
- format/JSON;
- summarization/extraction;
- stable factual;
- math reasoning;
- code generation;
- code debugging;
- long-context synthetic;
- tool-use simulation;
- adversarial/instruction hierarchy.

Cada execucao deve medir:

- modelo escolhido;
- custo estimado;
- tokens reais Fireworks;
- latencia;
- pass/fail mecanico;
- julgamento semantico local quando aplicavel;
- se o fallback teria escolhido melhor.
