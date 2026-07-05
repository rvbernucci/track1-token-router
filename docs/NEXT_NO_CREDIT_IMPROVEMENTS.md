# Next No-Credit Improvements

Atualizado em: 2026-07-05

## Leitura executiva

As Sprints 22-26 fecharam a primeira trilha de prontidao competitiva sem credito: modo competicao, fuzz pack, solvers deterministicos, runbooks de runtime e kit de submissao.

O projeto agora esta forte como runner. Os proximos ganhos sem credito nao estao em "mais um agente", mas em reduzir surpresa de julgamento, demonstracao, latencia, scoring e kickoff.

Base de leitura:

- `docs/COMPETITION_GAP_ANALYSIS.md`
- `SUBMISSION.md`
- `submission/`
- `docs/RUNBOOK_AMD_DIGITALOCEAN.md`
- `docs/RUNBOOK_FIREWORKS.md`
- `docs/RUNBOOK_GEMMA.md`
- `../AMD_Developer_Hackathon_Map.md`
- `../AMD_DigitalOcean_Infra_Map.md`
- `../FIREWORKS_OFFICIAL_DOCS_MAP.md`
- `../NATIVELYAI_NATIVE_BUILDER_MAP.md`

## Onde ainda nao exploramos o suficiente

| Area | O que ja temos | Lacuna sem credito | Risco |
|---|---|---|---|
| Demo URL | CLI, Docker, submission kit | Nao ha demo URL estatica ou landing page pronta | lablab pede aplicacao/prototipo acessivel por URL |
| Slides/video/cover | Roteiro, outline e brief | Ainda nao ha PDF, MP4 ou imagem final | Submissao pode parecer incompleta mesmo com codigo forte |
| Scoring oficial | Offline scoring e battle drill | Nao ha matriz de hipoteses do evaluator oficial | Podemos otimizar para proxy errado |
| Latencia | Timeouts em clients e fake provider | Nao ha gate de p95/cold start/concurrency | Resposta boa pode perder por tempo |
| Token accounting | Estimativa por prompt packet e usage real quando houver Fireworks | Nao ha envelope conservador por tokenizer/modelo | Budget remoto pode ser subestimado |
| Adapter hot-swap | Official adapter templates e fuzz pack | Nao ha "kickoff adapter drill" cronometrado | Formato oficial pode custar horas no dia 1 |
| Observabilidade | JSONL logs, trace analytics e reports | Nao ha dashboard/HTML estatico de traces | Jurado ve menos do que o sistema faz |
| Container de submissao | Dockerfile e CI Docker smoke | Docker nao embute scripts/reports/submission; e um runner enxuto | Otimo para evaluator, menos bom para demo standalone |
| Robustez de respostas | final validator basico | Pouca validacao semantica para respostas livres | Modelo local pode errar bonito e passar |
| Governanca de logs | secret scan | Ainda nao ha redacao/sanitizacao de prompt em logs | Risco ao compartilhar reports/demo |

## Melhorias recomendadas sem credito

### 1. Static Demo Pack

Criar uma pasta `demo-site/` ou `public-demo/` com HTML estatico gerado a partir de:

- arquitetura do router;
- exemplos reais de `ROUTER_MODE=competition`;
- `battle-report.md`;
- `fuzz-report.md`;
- `submission-readiness.md`;
- instrucoes de reproducao.

Aceite:

- roda localmente com `python3 -m http.server`;
- pode ser publicado no GitHub Pages;
- nao contem segredos, IPs ou logs sensiveis;
- explica o projeto para jurado em 90 segundos.

### 2. Artifact Build Kit

Transformar o que esta em `submission/` em artefatos finais:

- `slides.pdf`;
- `cover.png` ou `cover.jpg`;
- checklist de gravacao do video;
- roteiro com cenas e comandos exatos;
- pasta `submission/final/` ignorando arquivos grandes se necessario.

Aceite:

- readiness check valida existencia dos artefatos finais quando `--strict` for usado;
- materiais continuam alinhados com a narrativa do Track 1;
- nenhum artefato depende de credito.

### 3. Evaluator Assumptions Matrix

Criar `docs/EVALUATOR_ASSUMPTIONS.md` com hipoteses explicitas:

- input: texto, JSON, JSONL, arquivo, stdin;
- output: texto puro, JSON, JSONL;
- metricas: accuracy, token count, latencia, erro de parse;
- ambiente: container, env vars, endpoint local, Fireworks;
- proibicoes: rede, arquivos externos, logs no stdout.

Aceite:

- cada hipotese tem impacto, mitigacao e teste local;
- cada "unknown" vira pergunta de kickoff;
- o adapter oficial pode ser escolhido em menos de 30 minutos.

### 4. Latency And Timeout Lab

Expandir o fake provider e o battle drill para medir:

- cold start do CLI;
- tempo por task;
- tempo por lote JSONL;
- timeout local;
- timeout Fireworks simulado;
- p50/p95/p99 offline.

Aceite:

- novo script `scripts/latency_drill.py`;
- falha se p95 passar limite configurado;
- relatorio em `reports/generated/latency-report.md`;
- Docker smoke tambem mede tempo basico.

### 5. Token Envelope Lab

Criar um envelope conservador de tokens sem depender da Fireworks real:

- comparar estimativa atual `chars/4`;
- adicionar limites por rota;
- calcular pior caso por tarefa;
- mostrar "remote token exposure" por policy;
- destacar tarefas que quase estouram `MAX_REMOTE_TOKENS_PER_TASK`.

Aceite:

- `scripts/token_envelope.py`;
- relatorio com top 20 prompts mais caros;
- battle drill inclui `token_envelope_ready`;
- nenhum modelo remoto necessario.

### 6. Policy Optimizer Offline

Hoje temos perfis fixos. Podemos procurar fronteira de Pareto offline:

- varrer `repair_threshold`;
- varrer `remote_threshold`;
- varrer penalidade de budget;
- comparar exact match proxy, packet tokens e escalacao;
- salvar perfil candidato.

Aceite:

- `scripts/optimize_policy.py`;
- relatorio `policy-pareto.md`;
- nao substitui julgamento humano, mas revela sensibilidade.

### 7. Kickoff Adapter Drill

Simular o dia do kickoff:

- sortear um formato novo de input;
- criar adapter em tempo limitado;
- rodar fuzz pack;
- rodar release check;
- documentar tempo gasto.

Aceite:

- `docs/KICKOFF_ADAPTER_DRILL.md`;
- pelo menos tres formatos simulados;
- cada formato com fixture, adapter e teste;
- objetivo: adapter novo em menos de 30 minutos.

### 8. Log Redaction And Shareable Reports

Separar logs internos de reports publicos:

- redigir prompts longos;
- mascarar caminhos locais;
- bloquear IPs, hostnames privados e tokens;
- gerar `reports/public/`.

Aceite:

- `scripts/export_public_report.py`;
- reports publicos passam no `secret_scan`;
- demo-site usa apenas reports publicos.

### 9. Strict Submission Mode

Hoje `submission_readiness_check.py` valida textos base. Criar modo estrito para o dia final:

- exige URL de repo;
- exige URL de demo;
- exige caminho para video MP4;
- exige slides PDF;
- exige cover PNG/JPG;
- exige CI verde informado;
- exige benchmark real se creditos ja existirem.

Aceite:

- `python3 scripts/submission_readiness_check.py --strict`;
- warnings atuais viram erros no modo estrito;
- pode ser usado na ultima hora antes de submeter.

### 10. Decision Replay

Criar replay legivel de uma decisao:

- input;
- guardrail/solver;
- sinais de risco;
- budget;
- policy;
- packet remoto estimado;
- final validator;
- resposta final.

Aceite:

- `python3 scripts/replay_decision.py --text "..."`
- gera Markdown curto;
- util para video e para explicar arquitetura.

## Proximas 5 sprints sem credito recomendadas

### [Sprint 27 - Static Demo And Public Reports](../sprints/27-static-demo-public-reports/README.md)

- Criar demo-site estatico.
- Criar exportador de reports publicos.
- Criar GitHub Pages checklist.
- Atualizar submission demo URL checklist.

### [Sprint 28 - Evaluator Contract And Adapter Drill](../sprints/28-evaluator-contract-adapter-drill/README.md)

- Criar matriz de hipoteses do evaluator.
- Criar kickoff adapter drill.
- Adicionar tres adapters simulados.
- Medir tempo de adaptacao.

### [Sprint 29 - Latency And Token Envelope Lab](../sprints/29-latency-token-envelope-lab/README.md)

- Criar latency drill.
- Criar token envelope report.
- Integrar readiness ao battle drill.
- Definir p95 offline aceitavel.

### [Sprint 30 - Artifact Build Kit](../sprints/30-artifact-build-kit/README.md)

- Gerar slides PDF a partir do outline.
- Gerar cover PNG/JPG.
- Criar roteiro operacional de gravacao.
- Adicionar modo `--strict` ao readiness check.

### [Sprint 31 - Policy Pareto And Decision Replay](../sprints/31-policy-pareto-decision-replay/README.md)

- Criar policy optimizer offline.
- Criar decision replay Markdown.
- Atualizar video script com exemplos reais.
- Escolher perfil default com justificativa.

## Ordem de prioridade

1. `Sprint 27` porque lablab exige demo/prototipo acessivel por URL.
2. `Sprint 28` porque o maior risco tecnico no kickoff e contrato de input/output.
3. `Sprint 29` porque latency e token exposure podem matar uma arquitetura boa.
4. `Sprint 30` porque artefatos finais levam tempo e nao dependem de credito.
5. `Sprint 31` porque melhora narrativa tecnica e calibracao sem tocar em infra paga.

## O que nao fazer agora

- Nao construir UI complexa que vire dependencia do evaluator.
- Nao reescrever o core em outra linguagem.
- Nao adicionar banco vetorial sem corpus oficial.
- Nao criar RAG onde nao ha base de verdade.
- Nao depender de Native.Builder para o runtime competitivo.
- Nao otimizar para um benchmark que inventamos como se fosse o oficial.

## Conclusao

O projeto ja esta pronto para continuar sem credito. A tese agora e:

> transformar um runner tecnicamente forte em uma submissao impossivel de interpretar errado.

Isso significa demo clara, artefatos finais, adapter drill, latencia/token envelopes e replay de decisoes.
