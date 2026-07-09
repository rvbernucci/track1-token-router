# Runbook Fireworks Serverless

## Objetivo

Ativar Fireworks como auditor remoto compacto somente quando a cascata local escala.

Perfil recomendado: `runtime-profiles/fireworks-serverless.env.example`.

Nota Track 1 atual: local models sao uma estrategia valida de scoring. Respostas locais contam para accuracy e usam zero Fireworks tokens. Portanto Fireworks deve ser tratado como fallback/auditor no modo campeonato, nao necessariamente como caminho default.

## Variaveis obrigatorias

- `FIREWORKS_API_KEY`: nunca commitar.
- `ALLOWED_MODELS`: lista oficial injetada pelo harness; o runtime usa o primeiro modelo quando `FIREWORKS_MODEL` nao esta definido.
- `FIREWORKS_MODEL`: override local para desenvolvimento.
- `FIREWORKS_BASE_URL`: `https://api.fireworks.ai/inference/v1`.
- `FIREWORKS_SERVICE_TIER`: opcional; vazio usa Standard, `priority` so para fallback manual.

## Ativacao

```bash
cp runtime-profiles/fireworks-serverless.env.example .env.fireworks
printf "FIREWORKS_API_KEY=<set locally, not in git>\n" >> .env.fireworks.local
chmod 600 .env.fireworks.local
```

Carregar em shell local:

```bash
set -a
. ./.env.fireworks
. ./.env.fireworks.local
set +a
```

## Smoke real seguro

O smoke usa o mesmo cliente OpenAI-compatible do router, nunca imprime `FIREWORKS_API_KEY` e carrega `.env.fireworks` + `.env.fireworks.local` automaticamente se existirem.

```bash
python3 scripts/fireworks_smoke.py --json
```

Com modelo explicito:

```bash
python3 scripts/fireworks_smoke.py \
  --model accounts/fireworks/models/gemma-4-31b-it \
  --max-tokens 64 \
  --prompt "Answer with exactly one word: ready" \
  --json
```

Esperado:

- `ok=true`;
- `model` igual ao modelo testado;
- `usage.total` preenchido;
- nenhuma chave impressa no terminal.

Se Gemma retornar `HTTP 404` com `Model not found, inaccessible, and/or not deployed`, a chave Fireworks pode estar valida, mas o modelo Gemma ainda nao esta liberado para a conta/chave atual. Nesse caso, listar os modelos acessiveis pelo endpoint `/models` e usar temporariamente um modelo retornado por essa lista ate a liberacao do parceiro/hackathon.

Modelos com reasoning podem consumir poucos tokens apenas em `reasoning_content`. Para smoke real, evitar `--max-tokens 8`; usar `--max-tokens 64` ou maior para permitir uma resposta final em `message.content`.

Resultado de 2026-07-08:

- `accounts/fireworks/models/gemma-4-31b-it` retornou `HTTP 404 Not Found`;
- `accounts/fireworks/models/gemma-4-26b-a4b-it` retornou `HTTP 404 Not Found`;
- `accounts/fireworks/models/gemma-4-31b-it-nvfp4` retornou `HTTP 404 Not Found`;
- endpoint `/models` retornou `HTTP 403 Forbidden` para a chave atual;
- `accounts/fireworks/models/gpt-oss-20b` no smoke simples retornou resposta sem `message.content`, entao nao usar smoke simples para `gpt-oss`;
- `accounts/fireworks/models/deepseek-v4-flash` validou conectividade com `usage.total=59`, mas nao seguiu formato estrito no smoke; qualidade deve ser medida pelo microbench com validadores.
- `accounts/fireworks/models/minimax-m3` e `accounts/fireworks/models/kimi-k2p7-code` funcionaram com a chave atual e tambem funcionam quando chamados por alias curto via scripts do projeto.

## Microbench de reasoning

Em 2026-07-07, um microteste real com a chave Fireworks do projeto mostrou:

- prompt: `Answer with exactly one word: ready`;
- sem controle de reasoning, `glm-5p1` e `glm-5p2` gastaram 88-95 tokens e devolveram raciocinio no `content`;
- com `reasoning_effort=none`, `glm-5p1`, `deepseek-v4-pro`, `kimi-k2p6` e `glm-5p2` responderam em 13-18 tokens totais;
- `gpt-oss-120b` rejeitou `reasoning_effort=none`, mas aceitou `reasoning_effort=low`;
- o campo `reasoning=disabled` foi rejeitado pelo endpoint atual como input extra.

Implementacao atual:

- tarefas `cheap` e `medium` usam `reasoning_effort=none` quando o modelo nao e `gpt-oss`;
- `gpt-oss` usa `low` tambem em tarefas fortes, porque microbench com `medium` gerou content vazio/truncado com budget curto;
- se o modelo rejeitar o parametro, o runner refaz a chamada uma vez sem extra body.

## Microbench de Pareto

Em 2026-07-07, `scripts/fireworks_microbench.py` rodou 36 chamadas reais com 6 modelos e 6 tarefas mecanicamente validadas:

- custo estimado total: `0.00275120` USD;
- `deepseek-v4-flash`: 6/6 validas, custo `0.00011788`, media `1775ms`;
- `minimax-m3`: 6/6 validas, custo `0.00055590`, media `1508ms`;
- `kimi-k2p7-code`: 6/6 validas, custo `0.00112655`, media `1193ms`;
- `gpt-oss-20b`: 4/6 em auto, com falhas de content vazio em strong;
- `gpt-oss-120b`: 4/6 em auto, com falhas de content vazio/truncado em strong;
- `qwen3p7-plus`: 3/6, falhando por devolver raciocinio junto quando a tarefa exigia resposta estrita.

Teste complementar com `--reasoning-effort-override low` para `gpt-oss`:

- `gpt-oss-120b`: 6/6 validas, custo `0.00026265`, media `1805ms`;
- `gpt-oss-20b`: 5/6 validas, custo `0.00008870`, media `2436ms`;
- conclusao: `low` e o default seguro atual para `gpt-oss` com `max_tokens` curto.

Relatorios gerados:

- `reports/generated/fireworks-microbench-report.md`;
- `reports/generated/fireworks-microbench-gpt-low-report.md`.

Em 2026-07-08, apos receber creditos Fireworks, o microbench Pareto completo foi repetido com `--max-calls 36 --budget-usd 0.10`:

- chamadas: `36`;
- validas: `33/36`;
- tokens totais: `4835`;
- custo estimado: `0.00281451` USD;
- `deepseek-v4-flash`: 6/6, custo `0.00011788`, media `1699ms`;
- `gpt-oss-20b`: 6/6, custo `0.00012393`, media `1934ms`;
- `gpt-oss-120b`: 6/6, custo `0.00024825`, media `788ms`;
- `minimax-m3`: 6/6, custo `0.00055590`, media `1234ms`;
- `kimi-k2p7-code`: 6/6, custo `0.00112255`, media `1648ms`;
- `qwen3p7-plus`: 3/6, falhando por retornar raciocinio junto em tarefas estritas.

Vencedores por custo no dataset minimo de 2026-07-08:

- `formatting`: `deepseek-v4-flash`;
- `classification`: `deepseek-v4-flash`;
- `logic`: `deepseek-v4-flash`;
- `math_reasoning`: `gpt-oss-20b`;
- `code_generation`: `gpt-oss-20b`.

Vencedores por latencia no mesmo dataset:

- `format_json`, `math_reasoning` e `logic`: `gpt-oss-120b`;
- `code_generation`: `minimax-m3`;
- `cheap_exact_ack` e `cheap_sentiment`: `kimi-k2p7-code`, mas com custo maior que `deepseek-v4-flash`.

Smoke do contrato oficial em 2026-07-08:

```bash
ROUTER_MODE=fireworks \
ALLOWED_MODELS=accounts/fireworks/models/deepseek-v4-flash,accounts/fireworks/models/gpt-oss-20b,accounts/fireworks/models/gpt-oss-120b,accounts/fireworks/models/minimax-m3 \
python3 -m router submit-track1 \
  --input fixtures/official/lablab_track1_tasks.json \
  --output reports/generated/fireworks-official-smoke-results.json
```

Resultado:

- `/output/results.json` valido;
- tarefa de resumo usou Fireworks com `173` tokens remotos;
- tarefa aritmetica `6 * 7` saiu por solver deterministico com `0` tokens remotos;
- resposta final: `42`.

## Track 1 ACT II - Pareto Restrito Oficial

O guia Track 1 compartilhado em 2026-07-08 restringe os modelos a:

- `minimax-m3`;
- `kimi-k2p7-code`;
- `gemma-4-31b-it`;
- `gemma-4-26b-a4b-it`;
- `gemma-4-31b-it-nvfp4`.

O runtime normaliza aliases curtos para IDs Fireworks completos:

- `minimax-m3` -> `accounts/fireworks/models/minimax-m3`;
- `kimi-k2p7-code` -> `accounts/fireworks/models/kimi-k2p7-code`;
- `gemma-4-31b-it` -> `accounts/fireworks/models/gemma-4-31b-it`;
- `gemma-4-26b-a4b-it` -> `accounts/fireworks/models/gemma-4-26b-a4b-it`;
- `gemma-4-31b-it-nvfp4` -> `accounts/fireworks/models/gemma-4-31b-it-nvfp4`.

Smoke permitido em 2026-07-08:

- `minimax-m3`: OK, `162` tokens totais no smoke curto;
- `kimi-k2p7-code`: OK, `57` tokens totais no smoke curto;
- os tres Gemma: `HTTP 404 Not Found` na chave local atual.

Benchmark `evals/fireworks-pareto/track1-category-microbench.jsonl`, cobrindo as 8 categorias oficiais, com `minimax-m3` e `kimi-k2p7-code`:

- chamadas: `32`;
- validas mecanicas: `29/32`;
- custo estimado: `0.00517850` USD;
- `minimax-m3`: `15/16`, custo `0.00141390`, latencia media `1330ms`;
- `kimi-k2p7-code`: `14/16`, custo `0.00376460`, latencia media `2008ms`.

Falhas observadas:

- NER de data/dinheiro normalizou `July 8, 2026` para `2026-07-08` e `$450` para `450`; mecanicamente falhou, mas semanticamente provavelmente aceitavel;
- `kimi-k2p7-code` falhou em `debug_first_even` por devolver explicacao junto e codigo truncado;
- `reasoning_effort=none` global reduziu custo para `0.00282810` USD, mas piorou validade para `28/32`; portanto nao forcar `none` em tarefas fortes.

Politica atual para o caminho oficial:

- cheap/medium linguagem: Gemma-first quando Gemma estiver acessivel no harness;
- strong math/logic/code/debug: `minimax-m3` first;
- fallback entre modelos permitidos se o modelo escolhido retornar erro rapido de API, 404 ou resposta sem `message.content`;
- timeout nao cascata para outro modelo no mesmo request, porque o envelope oficial exige resposta abaixo de 30s;
- `kimi-k2p7-code` permanece como fallback/candidato, especialmente para codigo/logica, mas nao como default atual.
- se um modelo local confiavel estiver disponivel, `ROUTER_MODE=hybrid` deve ser comparado contra `ROUTER_MODE=fireworks`, porque respostas locais corretas custam zero Fireworks tokens.

Calibracao complementar de 2026-07-09 com todos os modelos permitidos esta em [`docs/FIREWORKS_TRACK1_ALLOWED_CALIBRATION.md`](./FIREWORKS_TRACK1_ALLOWED_CALIBRATION.md).

## Serverless vs Batch vs Deployments

Fireworks tem tres caminhos diferentes, e eles nao significam a mesma coisa para o Track 1.

O texto oficial do hackathon diz que Gemma pode ser acessado por Fireworks AI e AMD Developer Cloud, sem sign-up separado, e que existe premio de Track 1 para Best Use of Gemma via Fireworks. O mesmo texto tambem diz para checar as restricoes de cada track antes de escolher modelo.

### Serverless

Serverless e o caminho mais proximo do scoring do Track 1: chamada OpenAI-compatible em `FIREWORKS_BASE_URL` com modelo permitido em `ALLOWED_MODELS`.

Uso no projeto:

- `ROUTER_MODE=fireworks`;
- `python3 -m router submit-track1`;
- selecionar o menor modelo suficiente dentro de `ALLOWED_MODELS`.

Serving paths:

- Standard: default, sem `service_tier`.
- Priority: `service_tier=priority`; mais confiavel em pico, mas mais caro. Nao usar no caminho feliz de economia de creditos.
- Fast: nao e parametro; e outro model ID, como `accounts/fireworks/routers/glm-5p2-fast`. So usar se esse ID vier em `ALLOWED_MODELS` ou em teste local explicito.

Prompt cache:

- Fireworks ativa prompt caching por default.
- O router mantem o system prompt estatico no inicio e o input variavel no final.
- O runner envia `user=track1-token-router-v1` para dar uma pista de afinidade de sessao e aumentar chance de cache em prompts com prefixo comum.
- Nao colocar timestamp ou dados dinamicos no system prompt.

### Batch Inference Jobs

Batch e para inferencia assincrona em dataset JSONL. Ele pode mostrar modelos elegiveis para batch/on-demand, mas nao e o caminho natural do contrato oficial `/input/tasks.json` -> `/output/results.json`.

Riscos:

- pode ficar em `pending` se o modelo nao for compativel;
- depende de quota de batch;
- nao deve ser assumido como permitido no scoring final;
- pode consumir creditos sem melhorar a submissao oficial.

Uso aceitavel:

- avaliacao offline;
- gerar dataset de calibracao;
- testar prompt/router fora do harness.

### On-demand Deployments

Deployments criam GPUs dedicadas e permitem acessar modelos que nao existem em serverless. A Model Library pode mostrar Gemma como `Ready` e `Deploy on Demand`, mas isso nao significa que `accounts/fireworks/models/<gemma>` funcione diretamente no endpoint serverless.

Exemplo: em 2026-07-07, `accounts/fireworks/models/gemma-4-31b-it` aparece na Model Library como on-demand, mas `Serverless: Not supported`. Chamada direta em `/chat/completions` retorna `Model not found, inaccessible, and/or not deployed` enquanto nao houver deployment proprio ou liberacao especifica.

A documentacao oficial de On-Demand Deployments descreve esse caminho como deploy de um modelo em recurso dedicado, com consulta posterior via API OpenAI-compatible usando o deployment criado. Isso resolve acesso tecnico ao modelo, mas muda a natureza do risco: deixa de ser apenas escolha de modelo serverless e passa a envolver ciclo de vida de deployment.

Uso aceitavel:

- demonstrar Best Use of Gemma se o hackathon permitir esse caminho;
- calibrar Gemma fora do scoring;
- prototipar agente Gemma-first.

Risco para Track 1:

- deployment e cobrado por GPU-second;
- deployment pode continuar gerando custo se ficar ativo;
- deployment ID pode ser diferente do model ID listado em `ALLOWED_MODELS`;
- modelo de deployment pode nao estar em `ALLOWED_MODELS`;
- se nao passar por `FIREWORKS_BASE_URL` do harness, pode nao contar corretamente para o score.
- criar deployment dentro do container pode violar a ideia de ambiente padronizado e aumentar tempo de startup.

Perguntas que precisam de confirmacao antes de usar Gemma On-Demand no scoring:

- o harness vai injetar IDs serverless ou IDs de deployment em `ALLOWED_MODELS`?
- chamadas para deployment proprio contam para token efficiency?
- custo por GPU-second entra no score ou apenas tokens Fireworks?
- o deployment precisa existir antes da submissao ou pode ser criado pelo container?
- usar deployment proprio viola alguma restricao do Track 1?

Decisao operacional:

- final Track 1: `ALLOWED_MODELS` serverless-first, com fallback entre modelos permitidos;
- Gemma serverless liberado no harness: ativar Gemma-first em cheap/medium linguagem;
- Gemma apenas via On-Demand: usar como trilha de pesquisa/demo ate confirmacao explicita;
- nunca criar deployment automaticamente em script de teste sem aprovacao humana, porque pode abrir custo recorrente.

## Smoke hibrido

O modo hibrido exige endpoint local ativo.

```bash
ROUTER_MODE=hybrid \
python3 -m router ask "What is 2+2?" --json
```

Esperado para tarefa facil:

- rota local;
- `remote_tokens.total=0`.

Teste de escalacao controlada:

```bash
ROUTER_MODE=hybrid \
python3 -m router ask "Who is the CEO of AMD today?" --json
```

Esperado:

- chamada remota apenas se a cascata local escalar;
- resposta Fireworks em formato compacto `approve` ou `replace`;
- `remote_tokens` registrado.

## Modo oficial sem endpoint local

O Participant Guide injeta Fireworks, nao um endpoint local. Para o caminho oficial:

```bash
ROUTER_MODE=fireworks \
FIREWORKS_API_KEY=<harness-key> \
FIREWORKS_BASE_URL=<harness-base-url> \
ALLOWED_MODELS=<comma-separated-models> \
python3 -m router submit-track1 --input /input/tasks.json --output /output/results.json
```

Nesse modo, solvers deterministicos rodam antes da chamada remota e o primeiro modelo de `ALLOWED_MODELS` e usado quando `FIREWORKS_MODEL` estiver vazio.

## Budget guard

Antes de benchmark real:

```bash
export MAX_REMOTE_TOKENS_PER_TASK=300
export MAX_REMOTE_TOKENS_PER_RUN=6000
```

## Nao fazer

- Nao mandar todas as tasks direto para Fireworks sem medir.
- Nao aumentar `FIREWORKS_MAX_TOKENS` sem justificativa.
- Nao commitar `.env.fireworks.local`.
- Nao armazenar API key em logs ou screenshots.
