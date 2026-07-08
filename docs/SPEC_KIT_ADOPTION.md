# Spec Kit Adoption For Track 1 Token Router

## Por Que Isso Importa

O `github/spec-kit` formaliza Spec-Driven Development: especificacoes deixam de ser documentacao auxiliar e viram a fonte de verdade que guia plano, tarefas, testes e implementacao.

Para o hackathon, isso e especialmente forte porque nosso risco principal nao e apenas escrever codigo. Nosso risco e perder alinhamento entre:

- regra oficial do Track 1;
- estrategia de Pareto;
- matriz de capacidades dos modelos;
- restricoes de token/custo;
- testes offline;
- entrega Docker/CLI.

Spec Kit encaixa como governanca: antes de alterar o roteador, precisamos conseguir responder "qual requisito esta sendo atendido, qual teste prova isso, e qual decisao de scoring justifica a mudanca?".

## Principios A Adotar

### 1. Specification First

Toda mudanca competitiva relevante deve nascer de uma especificacao curta:

- problema;
- regra oficial impactada;
- decisao estrategica;
- comportamento esperado;
- criterio de aceite;
- teste ou evidencia.

### 2. Constitution Before Code

O projeto precisa de uma constituicao operacional. Para este Track 1:

- scoring manda;
- tokens Fireworks sao recurso escasso;
- accuracy abaixo do gate invalida economia;
- modelos auxiliares nao podem produzir resposta final;
- todo comportamento de rota precisa ser auditavel;
- nada depende de credito para evoluir offline;
- segredo nunca aparece em log, README, fixture ou CI.

### 3. Plan Then Tasks

Cada feature competitiva deve ter:

- `spec.md`: o que e por que;
- `plan.md`: como sera implementado;
- `tasks.md`: checklist executavel;
- testes vinculados;
- documentacao atualizada.

### 4. Test-First Where It Matters

Para logica de roteamento, primeiro definimos o comportamento em teste:

- tarefa cheap escolhe modelo barato suficiente;
- tarefa strong nao escolhe modelo underqualified;
- embedding/reranker nunca vencem chat;
- modelo caro so vence se houver ganho estrategico justificavel;
- metadata explica a decisao.

### 5. Converge After Implementation

Depois da implementacao, rodamos convergencia:

- especificacao ainda descreve o codigo?
- testes cobrem o comportamento prometido?
- docs explicam a decisao?
- o runbook permite reproduzir?
- a mudanca melhora scoring ou reduz risco?

## Fluxo Proposto Sem Instalar Nada Ainda

Enquanto nao decidirmos instalar o CLI oficial, adotamos a estrutura manual:

```text
specs/
  000-constitution/
    constitution.md
  001-fireworks-pareto-router/
    spec.md
    plan.md
    tasks.md
  002-game-theory-selection/
    spec.md
    plan.md
    tasks.md
```

Esse fluxo preserva compatibilidade mental com Spec Kit sem introduzir dependencia nova.

## Fluxo Proposto Com Spec Kit

Se decidirmos instalar:

```bash
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@vX.Y.Z
specify init . --integration codex
```

Antes disso, precisamos validar:

- se a integracao `codex` esta disponivel na versao instalada;
- se o comando nao sobrescreve arquivos existentes;
- quais arquivos seriam criados em `.specify/`, `specs/` ou diretorios de agente;
- se o projeto deve usar slash commands, skills mode ou apenas templates.

Comandos conceituais do Spec Kit:

- `constitution`: cria principios;
- `specify`: cria especificacao de feature;
- `plan`: traduz spec em plano tecnico;
- `tasks`: gera tarefas executaveis;
- `analyze`: verifica consistencia entre artefatos;
- `implement`: executa tarefas conforme plano.

## Como Isso Melhora Nosso Pareto

Sem Spec-Driven Development, cada heuristica pode virar opiniao.

Com Spec-Driven Development, cada heuristica precisa rastrear:

- fonte: regra oficial, model card, benchmark, smoke test ou eval offline;
- decisao: por que esse modelo entra ou sai;
- teste: como provar que a decisao nao regrediu;
- metrica: token, custo, latencia, accuracy, pass/fail mecanico;
- risco: onde a heuristica pode quebrar.

Exemplo:

```text
Spec: escolher menor modelo Fireworks suficiente.
Plan: calcular Pareto + Nash welfare por dominio.
Tasks: implementar matriz, metadata, testes e docs.
Tests: gpt-oss-20b vence cheap; MiniMax M3 vence code quando Kimi tem ganho marginal menor que custo; embedding nao vence chat.
```

## Regra De Adocao

Nao instalar Spec Kit ainda como dependencia do projeto principal.

Primeiro passo seguro:

- criar Sprint 39;
- criar constituicao manual;
- aplicar o fluxo a uma feature real;
- depois decidir se vale rodar `specify init`.

## Fontes

- GitHub Spec Kit repository: https://github.com/github/spec-kit
- Spec-Driven Development guide: https://raw.githubusercontent.com/github/spec-kit/main/spec-driven.md
- Spec Kit documentation: https://github.github.io/spec-kit/
