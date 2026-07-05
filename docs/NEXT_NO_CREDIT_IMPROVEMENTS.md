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

## Status apos Sprint 31

As Sprints 27-31 fecharam a segunda onda sem credito:

- demo estatica e reports publicos;
- adapter drill e matriz de hipoteses do evaluator;
- latency/token envelope;
- artifact build kit;
- policy Pareto e decision replay.

A terceira onda deve focar em publicar, ensaiar e endurecer os pontos de contato com mundo externo.

## Onde ainda nao exploramos o suficiente agora

| Area | O que ja temos | Lacuna sem credito | Risco |
|---|---|---|---|
| Demo publica | `demo-site/` e reports publicos | URL HTTPS ainda nao esta preenchida no strict readiness | lablab/jurados podem nao acessar a demo local |
| Strict readiness | `--strict` existe | Ainda falha por `demo_url` e `ci_status` pendente | Submissao final pode depender de memoria humana |
| Modelo local ruim | fake provider basico | Falta simular M1 bonito e errado, format drift e overconfidence | M2A pode aprovar erro plausivel |
| Respostas abertas | final validator e exact match | Falta harness semantico deterministico para respostas livres | Podemos calibrar apenas para formato e nao qualidade |
| Lote/timeout | latency drill por amostra | Falta stress de lote grande, falha parcial e throughput | Evaluator com batch grande pode estourar deadline |
| Logs/traces publicos | export de reports publicos | Falta redaction dedicada para logs JSONL e trace publico | Risco ao compartilhar material de debug |
| Ensaio de submissao | shotlist, slides, cover | Falta rehearsal completo cronometrado | Video/demo podem ficar improvisados |

## Segunda onda ja convertida em sprints 27-31

Esta secao fica como memoria das lacunas que ja viraram entregas executadas. A proxima fila acionavel esta na onda 3 abaixo.

### 1. Static Demo Pack

Criado em `demo-site/`, com HTML estatico gerado a partir de:

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

Transformado em pipeline de artefatos finais e placeholders controlados:

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

Criado em `docs/EVALUATOR_ASSUMPTIONS.md` com hipoteses explicitas:

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

Implementado com latency drill e battle drill para medir:

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

Criado envelope conservador de tokens sem depender da Fireworks real:

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

Criado para procurar fronteira de Pareto offline:

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

Criado para simular o dia do kickoff:

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

Criado para separar reports publicos de artefatos internos:

- redigir prompts longos;
- mascarar caminhos locais;
- bloquear IPs, hostnames privados e tokens;
- gerar `reports/public/`.

Aceite:

- `scripts/export_public_report.py`;
- reports publicos passam no `secret_scan`;
- demo-site usa apenas reports publicos.

### 9. Strict Submission Mode

Adicionado em `submission_readiness_check.py` para o dia final:

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

Criado como replay legivel de uma decisao:

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

## Proximas 5 sprints sem credito recomendadas - onda 3

### [Sprint 32 - Public Demo Deploy And Strict Readiness](../sprints/32-public-demo-deploy-strict-readiness/README.md)

- Publicar `demo-site/` em URL HTTPS.
- Criar check local da demo.
- Atualizar `submission/final/submission-status.json`.
- Aproximar o strict readiness do estado final.

### [Sprint 33 - Bad Local Model Chaos Lab](../sprints/33-bad-local-model-chaos-lab/README.md)

- Simular modelos locais ruins.
- Medir false approval rate.
- Proteger M2A/policy/final validator contra respostas plausiveis erradas.
- Criar gate de regressao para confianca local.

### [Sprint 34 - Semantic Validation Harness](../sprints/34-semantic-validation-harness/README.md)

- Criar dataset semantico.
- Criar rubricas offline deterministicas.
- Medir aceitabilidade alem de exact match.
- Classificar respostas parciais, perigosas e verbosas.

### [Sprint 35 - Batch Throughput And Timeout Stress](../sprints/35-batch-throughput-timeout-stress/README.md)

- Criar stress de lote grande.
- Medir throughput e falha parcial.
- Definir envelope de timeout por lote.
- Preparar eventual modo concorrente apenas se necessario.

### [Sprint 36 - Submission Rehearsal And Log Redaction](../sprints/36-submission-rehearsal-log-redaction/README.md)

- Criar redaction de logs/traces.
- Criar ensaio de submissao cronometrado.
- Gerar trace publico seguro.
- Fechar ritual de video, demo, CI e checklist.

## Sprints 27-31 executadas

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

1. `Sprint 32` porque lablab/jurados precisam de URL HTTPS e o strict readiness ainda aponta essa lacuna.
2. `Sprint 33` porque modelo local ruim e confiante e o risco tecnico mais perigoso sem credito.
3. `Sprint 34` porque exact match nao cobre respostas livres e qualidade semantica.
4. `Sprint 35` porque batch, timeout e falha parcial podem quebrar scoring mesmo com boas respostas.
5. `Sprint 36` porque video, logs publicos e ensaio de submissao precisam virar ritual reproduzivel.

## O que nao fazer agora

- Nao construir UI complexa que vire dependencia do evaluator.
- Nao reescrever o core em outra linguagem.
- Nao adicionar banco vetorial sem corpus oficial.
- Nao criar RAG onde nao ha base de verdade.
- Nao depender de Native.Builder para o runtime competitivo.
- Nao otimizar para um benchmark que inventamos como se fosse o oficial.

## Conclusao

O projeto ja esta pronto para continuar sem credito. A tese agora e:

> transformar um runner tecnicamente forte em uma submissao publicada, ensaiada e resistente a modelos locais ruins.

Isso significa URL publica, strict readiness quase final, caos de modelo local, validacao semantica, stress de lote e redaction de logs.
