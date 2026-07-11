# Model Capability Research For Pareto Routing

## Objective

This document converts official pages, model cards, and technical reports into practical routing criteria for Track 1.

The final Pareto frontier should not just be `lowest price`. It should combine:

- estimated input/output cost;
- proven capability per domain;
- risk of overthinking and reasoning tokens;
- chat/completions support;
- tool/function calling support when relevant;
- evidence confidence: paper/model card > official launch note > provider listing > internal benchmark without open methodology.

## Golden Rule

The router should first ask: "what is the smallest model that is good enough for this domain?".

If the task is simple, cost wins. If the task is complex, the model needs to pass a capability floor before competing on cost. If the task depends on an auxiliary tool, embedding/reranker only enter if there is actual RAG/ranking; they must never produce the final response.

## Executive Map

| Family / Fireworks models | Best use in the Pareto | Input signal | Caveat |
| --- | --- | --- | --- |
| `gpt-oss-20b` | classification, short format, simple responses | label, sentiment, simple JSON, short response | higher risk of hallucination/factual errors than larger models |
| `gpt-oss-120b` | cheap general reasoning, tool use, structured output | logic, math, general hard, requires good cost-efficiency | `reasoning_effort=low/medium`; `none` may be rejected |
| `deepseek-v4-flash` | cheap general/medium, reasoning with budget, summarization | medium questions, general language, simple agentic | do not treat as Pro in deep knowledge or highly complex agents |
| `deepseek-v4-pro` | high-confidence reasoning/code/knowledge | hard STEM, hard code, hard knowledge | expensive and slow; use when lower-cost options fail or task requires high confidence |
| `kimi-k2p7-code` | long-horizon coding and agentic coding | write/debug/refactor code, multi-step tool calls | always thinking; can consume output tokens if output is not controlled |
| `kimi-k2p6` | Kimi fallback for code/agents | strong code if K2.7 is not released | K2.7 improves token efficiency and benchmarks |
| `minimax-m3` | best cost/capability candidate for code/agents in current catalog | coding, bugfix, terminal, agent, multimodal | official/vendor benchmarks; validate in our eval |
| `minimax-m2p7` | cheap fallback for agent/productivity/code | office, tool-use, code, SRE-style tasks | inferior to M3 in context/multimodality |
| `qwen3p7-plus` | balanced multimodal/tool/coding model | multimodal, GUI, tool use, multilingual | low transparency specific to Plus; use Qwen3/Qwen3.7 as proxy |
| `glm-5p2` | long-horizon coding, repo-scale context, engineering constraints | large repos, long refactoring, 1M context | more expensive than M3/Qwen/DeepSeek Flash |
| `glm-5p1` | long-horizon engineering fallback | agent/code when 5.2 is unavailable | 5.2 outperforms 5.1 in coding and context |
| `nemotron-3-ultra-nvfp4` | agentic reasoning, math/code/science with throughput | long tasks, planning, tool calling, 1M context | medium price; might be too powerful for cheap/medium |
| `qwen3-embedding-8b` | embedding for RAG/search | needs to search context in a corpus | not a final response model |
| `qwen3-reranker-8b` | reranking for RAG/search | candidate document list exists | not a final response model |

## Evidence By Family

### OpenAI gpt-oss-20b / gpt-oss-120b

Official sources:

- [OpenAI gpt-oss model card](https://openai.com/index/gpt-oss-model-card/)
- [OpenAI introducing gpt-oss](https://openai.com/index/introducing-gpt-oss/)
- [OpenAI gpt-oss GitHub](https://github.com/openai/gpt-oss)
- [gpt-oss arXiv model card](https://arxiv.org/html/2508.10925v1)

Training and architecture:

- open-weight text-only models, Apache 2.0;
- MoE Transformer;
- `gpt-oss-120b`: 117B total parameters, 5.1B active/token, 128k context;
- `gpt-oss-20b`: 21B total parameters, 3.6B active/token, 128k context;
- text-only dataset focusing on STEM, coding, and general knowledge;
- post-training with SFT and high-compute RL for reasoning and tool use;
- tokenizer `o200k_harmony`; using correct Harmony/chat template matters.

Where it performs best:

- `gpt-oss-120b`: general reasoning, math, tool use, structured outputs, function calling;
- `gpt-oss-20b`: simple, specialized tasks with low latency/cost;
- OpenAI reports `gpt-oss-120b` close to `o4-mini` on core benchmarks and `gpt-oss-20b` comparable to `o3-mini` on common benchmarks.

Pareto risks:

- OpenAI reports worse performance than `o4-mini` on SimpleQA/PersonQA; this signals factual accuracy risks without search;
- instruction hierarchy and prompt-injection defenses are weaker than `o4-mini`;
- for Track 1, `gpt-oss-20b` should be cheap-first; `gpt-oss-120b` should be reasoning-budget-first.

Routing decision:

- `gpt-oss-20b`: cheap/default for simple classification and formatting.
- `gpt-oss-120b`: medium/strong when the domain is logic/math/general and cost needs to be kept low.
- Avoid for current factual questions without external tools; if used, require short responses and explicit uncertainty.

### DeepSeek V4 Flash / DeepSeek V4 Pro

Official sources:

- [DeepSeek V4 Preview Release](https://api-docs.deepseek.com/news/news260424)
- [DeepSeek-V4-Pro Hugging Face model card](https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro)
- [DeepSeek-V4-Pro NVIDIA NIM model card](https://build.nvidia.com/deepseek-ai/deepseek-v4-pro/modelcard)

Training and architecture:

- MoE with 1M context;
- `DeepSeek-V4-Pro`: 1.6T total parameters, 49B active;
- `DeepSeek-V4-Flash`: 284B total parameters, 13B active;
- hybrid attention with CSA + HCA to reduce long context costs;
- mHC for signal stability;
- Muon optimizer;
- pretraining on over 32T tokens according to the HF model card;
- post-training in two stages: domain experts with SFT + GRPO, then consolidation via on-policy distillation;
- `Non-think`, `Think High`, `Think Max` modes.

Where it performs best:

- Pro: math/STEM/coding, world knowledge, complex agents, long context;
- Flash: reasoning close to Pro when given a thinking budget, good for simple agentic tasks, faster and more economical;
- official benchmark shows Pro Max strong in LiveCodeBench, Codeforces, GPQA Diamond, HMMT, IMOAnswerBench, Terminal Bench, SWE Verified/Pro, BrowseComp, and Toolathlon.

Pareto risks:

- Flash should not automatically inherit the same capability floor as Pro for deep knowledge and complex agents;
- Pro may dominate on quality, but is expensive/slow;
- thinking modes can blow up token counts if there is no output limit.

Routing decision:

- `deepseek-v4-flash`: cheap medium-general and reasoning when `gpt-oss-120b` is not sufficient or when there is good cost/latency.
- `deepseek-v4-pro`: strong fallback for math/coding/agent/knowledge when cheaper models fail or when the input signals high complexity.

### Moonshot Kimi K2.7 Code / Kimi K2.6

Official sources:

- [Kimi K2.7 Code official docs](https://platform.kimi.ai/docs/guide/kimi-k2-7-code-quickstart)
- [Kimi K2.7 Code Hugging Face model card](https://huggingface.co/moonshotai/Kimi-K2.7-Code)
- [Kimi K2 GitHub](https://github.com/moonshotai/kimi-k2)
- [Moonshot AI homepage](https://www.moonshot.ai/)

Training and architecture:

- K2 family: MoE, 1T total, 32B active, Muon optimizer lineage;
- Kimi K2 base was pre-trained on 15.5T tokens according to the Kimi K2 repository;
- K2.7 Code is built on K2.6 and optimized for coding-focused agentic work;
- K2.7 Code: 1T total, 32B active, 256K context, MLA attention, MoonViT vision encoder;
- supports image/video input in official API;
- K2.7 Code does not support non-thinking mode.

Where it performs best:

- long-horizon coding;
- instruction compliance in long contexts;
- multi-step tool invocation;
- agentic coding workflows;
- Kimi reports K2.7 Code improves over K2.6 in coding and agentic benchmarks and reduces overthinking tendencies by around 30%.

Highlighted benchmarks:

- Kimi Code Bench v2: K2.6 50.9, K2.7 Code 62.0;
- Program Bench: K2.6 48.3, K2.7 Code 53.6;
- MCP Atlas: K2.6 69.4, K2.7 Code 76.0;
- MCP Mark Verified: K2.6 72.8, K2.7 Code 81.1.

Pareto risks:

- always thinking means risk of high output token counts;
- for trivial tasks, it is wasteful;
- for Track 1, it needs a short final response prompt if invoked.

Routing decision:

- `kimi-k2p7-code`: strong code, debugging, agentic coding, long-horizon code, multimodal tool tasks.
- `kimi-k2p6`: fallback if K2.7 Code is not in `ALLOWED_MODELS`.
- Avoid for classification/short format.

### Z.ai GLM-5.2 / GLM-5.1

Official sources:

- [GLM-5.2 official docs](https://docs.z.ai/guides/llm/glm-5.2)
- [GLM-5.1 official docs](https://docs.z.ai/guides/llm/glm-5.1)
- [GLM 5.2 Fireworks model page](https://fireworks.ai/models/fireworks/glm-5p2)
- [GLM 5.1 Fireworks model page](https://fireworks.ai/models/fireworks/glm-5p1)

Training and architecture:

- GLM-5.2: flagship foundation model, text-in/text-out, 1M context, 128K max output;
- GLM-5.1: flagship model for long-horizon tasks, 200K context, 128K max output;
- Fireworks lists GLM-5.2 as 743B MoE and GLM-5.1 as 754B-parameter MoE;
- Z.ai discloses specialized training for long-horizon coding and engineering workflows, but not a full data recipe in the docs we found.

Where it performs best:

- long-horizon engineering;
- repo-scale codebase understanding;
- refactoring with constraints;
- mobile/on-device debugging loops;
- production-grade standard adherence;
- code-to-video / engineering artifacts.

Highlighted benchmarks:

- GLM-5.2 docs report Terminal-Bench 2.1: 81.0 and SWE-bench Pro: 62.1;
- GLM-5.1 docs report SWE-Bench Pro: 58.4 and broad agent/coding/tool/browsing strength.

Pareto risks:

- output price is higher than M3, Qwen, and gpt-oss;
- can be excellent for hard long-horizon, but should not enter cheap;
- 5.2 seems to replace 5.1 for code/long context tasks.

Routing decision:

- `glm-5p2`: strong-long-context, repo-scale, engineering with constraints, tasks where full context is worth the cost.
- `glm-5p1`: fallback if 5.2 is not released.
- Avoid for short tasks, classification, and simple JSON.

### MiniMax M3 / MiniMax M2.7

Official sources:

- [MiniMax M3 official blog](https://www.minimax.io/blog/minimax-m3)
- [MiniMax M3 Hugging Face model card](https://huggingface.co/MiniMaxAI/MiniMax-M3)
- [MiniMax M3 NVIDIA NIM model card](https://build.nvidia.com/minimaxai/minimax-m3/modelcard)
- [MiniMax M2.7 GitHub](https://github.com/MiniMax-AI/MiniMax-M2.7)
- [MiniMax M2.7 NVIDIA NIM model card](https://build.nvidia.com/minimaxai/minimax-m2.7/modelcard)

Training and architecture:

- M3: multimodal MoE, around 428B total, around 22-23B active, 1M context;
- M3 uses MiniMax Sparse Attention (MSA) to scale 1M context efficiently;
- M3 undergoes mixed-modality training from the first step and uses interleaved multimodal data;
- M3 supports thinking `enabled`, `adaptive`, and `disabled`;
- M2.7: MoE, around 230B total, 10B active, 204,800 context;
- M2.7 training data is not fully disclosed, but MiniMax reports self-evolution loops and RL experiment scaffolds.

Where it performs best:

- M3: coding, agentic work, long-context, multimodal, video/image understanding, desktop/computer operation;
- M2.7: complex software engineering, production troubleshooting, office productivity, document editing, agent teams, tool use.

Highlighted benchmarks:

- M3 official blog: SWE-Bench Pro 59.0, Terminal-Bench 2.1 66.0, SWE-fficiency 34.8, KernelBench Hard 28.8, MCP Atlas 74.2;
- M2.7 GitHub/NIM: SWE-Pro 56.22, VIBE-Pro 55.6, Terminal Bench 2 57.0, NL2Repo 39.8, GDPval-AA 1495 ELO, Toolathon 46.3, MM Claw 62.7, MLE Bench Lite 66.6% medal rate.

Pareto risks:

- M3/M2.7 benchmarks are mostly reported by the vendor or provider model cards; we need to validate them in our eval;
- M3 is an excellent candidate because it combines low price with high capability, but the router should not assume that it always beats DeepSeek/Kimi/GLM for all code.

Routing decision:

- `minimax-m3`: default strong-code/agentic if `ALLOWED_MODELS` includes it and the input does not require deep knowledge better covered by DeepSeek Pro.
- `minimax-m2p7`: cheap fallback for code/agent/productivity if M3 is not released.
- M3 with `thinking=disabled/adaptive` and short prompts can be a token advantage.

### Qwen3.7 Plus / Qwen3 Embedding / Qwen3 Reranker

Official sources:

- [Qwen3.7 official blog](https://qwen.ai/blog?id=qwen3.7)
- [Qwen3 technical report](https://arxiv.org/html/2505.09388v1)
- [Qwen docs](https://qwen.readthedocs.io/)
- [Qwen3 Embedding paper](https://arxiv.org/html/2506.05176v1)
- [Qwen3 Embedding GitHub](https://github.com/QwenLM/Qwen3-Embedding)
- [Qwen3.7 Plus Fireworks model page](https://fireworks.ai/models/fireworks/qwen3p7-plus)
- [Qwen3 Embedding 8B Fireworks model page](https://fireworks.ai/models/fireworks/qwen3-embedding-8b)
- [Qwen3 Reranker 8B Fireworks model page](https://fireworks.ai/models/fireworks/qwen3-reranker-8b)

Training and architecture:

- Qwen3 family includes dense and MoE models from 0.6B to 235B;
- Qwen3 technical report describes unified thinking/non-thinking modes and thinking budget;
- Qwen3 expands multilingual coverage to 119 languages/dialects;
- Qwen3.7 Plus is listed by Fireworks as a serverless customized Qwen model with function calling and image input;
- Qwen3 Embedding/Reranker are built from Qwen3 foundation models and trained through multi-stage unsupervised pre-training + supervised fine-tuning with synthetic data generation/merging.

Where it performs best:

- Qwen3 family: multilingual, math, coding, general reasoning, agent/tool tasks;
- Qwen3.7 Plus: likely cost-effective multimodal/tool/general model when image input matters;
- Qwen3 Embedding 8B: multilingual embedding, code retrieval, cross-lingual retrieval;
- Qwen3 Reranker 8B: ranking/retrieval relevance after candidate retrieval.

Highlighted benchmarks:

- Qwen3 technical report: Qwen3 models improve coding/math/general/multilingual baselines; Qwen3-32B improves EvalPlus/MultiPL-E/MBPP/CRUX-O vs comparable models;
- Qwen3 Embedding paper: Qwen3-8B-Embedding scores 70.58 on MTEB Multilingual and 80.68 on MTEB Code, with strong reranking results.

Pareto risks:

- Qwen3.7 Plus specific training recipe is less transparent than open Qwen3 papers;
- embedding/reranker burn Fireworks tokens but do not answer the user;
- for Track 1, auxiliary retrieval only makes sense if the benchmark task includes documents/corpus where retrieval improves accuracy enough to pay for itself.

Routing decision:

- `qwen3p7-plus`: medium/strong general, multimodal, function-calling, multilingual, when price/capability beats GLM/Kimi/DeepSeek.
- `qwen3-embedding-8b`: never answer final; only future RAG.
- `qwen3-reranker-8b`: never answer final; only future reranking.

### NVIDIA Nemotron 3 Ultra NVFP4

Official sources:

- [NVIDIA Nemotron 3 Ultra NIM model card](https://build.nvidia.com/nvidia/nemotron-3-ultra-550b-a55b/modelcard)
- [Nemotron 3 Ultra arXiv](https://arxiv.org/abs/2606.15007)
- [NVIDIA Nemotron 3 Ultra research page](https://research.nvidia.com/labs/nemotron/Nemotron-3-Ultra/)

Training and architecture:

- 550B total, 55B active;
- hybrid Mamba-Transformer MoE with LatentMoE;
- 1M context;
- NVFP4 pre-training recipe;
- around 20T text tokens;
- SFT, RL, Multi-teacher On-Policy Distillation;
- multi-environment RLVR across math, code, science, instruction following, tool use, multi-turn conversation and structured output;
- training data disclosed more extensively than most providers.

Where it performs best:

- long-running autonomous agentic tasks;
- planning, tool calling, math, code, science;
- high-throughput inference relative to similarly capable public models;
- cases where open model transparency/data disclosure matters.

Highlighted benchmarks/claims:

- NVIDIA reports around 5x to 6x throughput advantage versus comparable open models while maintaining frontier-class accuracy;
- model card emphasizes agentic reasoning, code/math/science, long-context analysis and complex multi-step agents.

Pareto risks:

- stronger than needed for cheap/medium tasks;
- may be expensive relative to gpt-oss/deepseek-flash/minimax;
- route only when strong reasoning/agentic confidence is required.

Routing decision:

- `nemotron-3-ultra-nvfp4`: strong fallback for complex agentic reasoning, math/code/science, tool calling, long context.
- Do not use for short classification/format tasks.

## Proposed Tiers for the Router

### Cheap

Objective: spend the minimum on nearly deterministic tasks or short language prompts.

Preferred models:

- `gpt-oss-20b`
- `deepseek-v4-flash` if `gpt-oss-20b` fails/is not released
- `gpt-oss-120b` if the simple task requires a bit more reasoning and is still cheap

Avoid:

- Kimi, GLM, DeepSeek Pro, Nemotron, M3 for trivial tasks.

### Medium

Objective: maintain good quality without triggering an expensive model.

Preferred models:

- `gpt-oss-120b`
- `deepseek-v4-flash`
- `qwen3p7-plus`
- `minimax-m3` if the task involves light code/agent behavior

Signals:

- general explanation;
- summarization;
- extraction;
- stable factual question;
- short multi-turn;
- multilingual.

### Strong Code / Agent

Objective: get tasks right where an incorrect answer drops accuracy.

Preferred models:

- `minimax-m3` for the best initial cost/capability;
- `kimi-k2p7-code` when long-horizon code and confidence matter;
- `glm-5p2` when 1M context/repo-scale is essential;
- `deepseek-v4-pro` when coding + reasoning + knowledge require high confidence;
- `nemotron-3-ultra-nvfp4` when agent/tool/long planning and throughput matter.

### Strong Math / Reasoning / STEM

Preferred models:

- `gpt-oss-120b` if cost is the priority;
- `deepseek-v4-pro` if the task resembles olympiads/competitive STEM/coding;
- `nemotron-3-ultra-nvfp4` for math/science/tool reasoning;
- `qwen3p7-plus` as a middle ground if allowed.

### Long Context

Preferred models:

- `glm-5p2`: 1M context and focus on long-horizon engineering;
- `deepseek-v4-pro` / `deepseek-v4-flash`: 1M context with CSA/HCA;
- `minimax-m3`: 1M context with MSA and multimodal;
- `nemotron-3-ultra-nvfp4`: 1M context and agentic reasoning.

### RAG / Retrieval

Auxiliary models:

- `qwen3-embedding-8b`: embedding;
- `qwen3-reranker-8b`: reranking.

Rule: only use if there is an external corpus/candidate documents. If the input is just an open question, embedding/reranker will likely burn tokens without increasing accuracy.

## Suggested Pareto Changes

1. Add `capability_by_domain`, not just `strengths`.
2. Separate `strong_code`, `strong_math`, `long_context`, `agentic_tool`, `multimodal`, `factual`.
3. Add `thinking_token_risk`: low, medium, high.
4. Add `evidence_confidence`: official-paper, official-doc, provider-card, internal-benchmark.
5. Add `mode_policy`: non-thinking, low, medium, high, adaptive, forced-thinking.
6. Keep embedding/reranker out of the final response.
7. Run a small microbench per domain when credits allow, because vendor benchmarks do not replace the hackathon's scoring.

## Competitive Hypotheses

- For cheap tasks, `gpt-oss-20b` tends to be the champion if output is rigidly short.
- For cheap reasoning, `gpt-oss-120b` may offer the best accuracy/cost ratio, but care must be taken with hallucination.
- For code, `minimax-m3` is the number 1 candidate for price/capability; Kimi K2.7 Code and GLM-5.2 may win on long-horizon code but cost more tokens.
- For hard math/STEM, DeepSeek Pro and Nemotron should enter as high-confidence fallbacks.
- For multimodal/GUI/video, Qwen3.7 Plus, Kimi K2.7 Code, and MiniMax M3 are the most relevant candidates, but this only matters if Track 1 actually brings multimodal input.
- For long context, use 1M-context models only if input exceeds a size limit or contains a corpus/project; otherwise, it is a waste of budget.

## Next Steps

Create a local micro-eval with 5 to 10 prompts per domain:

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

Each run should measure:

- model chosen;
- estimated cost;
- actual Fireworks tokens;
- latency;
- mechanical pass/fail;
- local semantic judgment when applicable;
- whether the fallback would have chosen better.
