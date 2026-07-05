# Builder Plan

Plano de construcao do `Track 1 Token Router CLI`.

Este documento organiza a estrategia-mestra. A execucao detalhada fica em [`../sprints`](../sprints/README.md).

## Norte

Construir um agente competitivo para o `Track 1 - Hybrid Token-Efficient Routing Agent`.

O projeto nao e um chatbot generico. E um runner de competicao:

- recebe uma tarefa desconhecida;
- gera uma resposta local barata;
- valida localmente com uma segunda passada mais criteriosa;
- escala para Fireworks apenas quando o risco de erro compensa o custo;
- registra metricas para calibrar qualidade, tokens e latencia;
- roda em container de forma reproduzivel.

## Hipoteses de trabalho

- As tarefas reais so serao reveladas no kickoff.
- O input principal deve ser tratado como texto, mas o envelope precisa aceitar arquivos e metadados.
- Tokens locais nao contam no score, mas tempo, estabilidade e memoria importam.
- Tokens remotos contam e devem ser usados como seguro de qualidade, nao como caminho padrao.
- A resposta final deve preservar o formato pedido pela tarefa original.
- JSON/XML devem ser usados para controle interno, nao para forcar respostas livres.

## Arquitetura alvo

```text
TaskEnvelope
  -> M1 local sem reasoning
      gera candidato livre
  -> M2A local com reasoning
      valida candidato e decide approve/escalate
  -> se approve
      entrega candidato do M1
  -> se escalate
      M2B local com reasoning gera alternativa livre
  -> Fireworks auditor
      aprova M2B ou substitui por resposta remota
  -> FinalAnswer
```

## Principios de estado da arte

- Contratos pequenos e estaveis antes de prompts longos.
- Observabilidade desde o primeiro dia: rota, tokens, latencia, erros e decisao.
- Prompts versionados como codigo.
- Separacao entre geracao livre e decisao estruturada.
- Saida limpa no `stdout`; logs e debug fora do caminho do avaliador.
- Testes com golden set, edge cases e adversarial prompts.
- Ablation tests para provar se cada etapa melhora ou so adiciona custo.
- Fallback seguro quando modelo local, Fireworks ou parsing falhar.
- Container reproduzivel antes da ultima sprint, nao no ultimo dia.
- Otimizacao por Pareto: qualidade suficiente com o menor token remoto possivel.

## Sprints concluidas

| Sprint | Tema | Resultado esperado |
|---|---|---|
| 01 | Fundacao e contratos | CLI minimo, contratos, logs e esqueleto testavel. |
| 02 | Modelo local e M1 | Cliente local, geracao livre e baseline sem Fireworks. |
| 03 | Verificador M2A e M2B | Cascata local com decisao approve/escalate e alternativa. |
| 04 | Fireworks e scoring | Auditor remoto, token accounting, eval harness e calibracao. |
| 05 | Hardening e entrega | Docker, robustez, README publico e pacote de submissao. |

## Roadmap sem credito

Esta e a rota principal enquanto os creditos AMD/Fireworks nao forem liberados. As sprints 06-11 ja foram executadas como pacote offline.

| Sprint | Tema | Resultado esperado |
|---|---|---|
| 06 | Offline Evaluation Arena | Dataset grande, adversarial e medivel sem provedores reais. |
| 07 | Routing Policy Lab | Modos `aggressive`, `balanced`, `conservative` calibrados offline. |
| 08 | Fake Provider Chaos Lab | Simuladores de local/Fireworks com latencia, falhas e custos falsos. |
| 09 | Official Adapter Readiness | Estrutura para adaptar rapido ao formato oficial no kickoff. |
| 10 | Offline Release Candidate | Release candidate que roda sem credito e esta pronto para plugar credenciais. |
| 11 | Testing Culture Lab | Playground, matriz de testes e cultura de promocao para regressao automatizada. |
| 12 | Offline Scoring Simulator | Leaderboard offline com accuracy, tokens, latencia e parse failures. |
| 13 | Prompt Versioning & Ablation Lab | Prompts versionados e comparaveis sem modelo real. |
| 14 | Deterministic Guardrails | Respostas deterministicas seguras antes da cascata. |
| 15 | Trace Analytics | Relatorios a partir de logs JSONL. |
| 16 | Release Automation & GHCR | Release notes e publicacao de imagem em tags. |

## Roadmap dependente de credito

Esta trilha nao bloqueia a rota principal. Ela comeca quando houver acesso real.

| Sprint | Depende de | Resultado esperado |
|---|---|---|
| Credit A | AMD Developer Cloud | Modelo local real rodando em endpoint OpenAI-compatible. |
| Credit B | Fireworks | Auditor remoto real calibrado com tokens reais. |
| Credit C | AMD + Fireworks | Benchmark end-to-end de custo, latencia e qualidade. |
| Credit D | AMD + Fireworks + kickoff | Ensaio final no ambiente mais parecido com scoring oficial. |

## Definition of Done global

- O projeto roda por CLI com `ask`, `solve`, `run` e `eval`.
- O runner aceita stdin, arquivo, JSON e JSONL.
- Cada task gera um log JSONL auditavel.
- O Fireworks so e chamado em rotas justificadas.
- Existe uma suite de avaliacao local com casos faceis, medios, dificeis e adversariais.
- O container roda do zero com env vars documentadas.
- O README explica instalacao, execucao, arquitetura e tradeoffs.
- A submissao nao depende de estado local escondido.

## Ritmo de trabalho

- Comecar cada sprint com um contrato pequeno.
- Terminar cada sprint com um comando executavel.
- Nunca deixar uma melhoria sem metrica.
- Toda decisao de arquitetura deve responder:
  - melhora accuracy?
  - reduz token remoto?
  - reduz risco no scoring?
  - melhora reproducibilidade?
  - ou e so complexidade bonita?
