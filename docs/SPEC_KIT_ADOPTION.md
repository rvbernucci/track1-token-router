# Spec Kit Adoption For Track 1 Token Router

## Why This Matters

The `github/spec-kit` formalizes Spec-Driven Development: specifications stop being auxiliary documentation and become the source of truth that guides the plan, tasks, tests, and implementation.

For the hackathon, this is especially strong because our main risk is not just writing code. Our risk is losing alignment between:

- official Track 1 rules;
- Pareto strategy;
- model capability matrix;
- token/cost constraints;
- offline tests;
- Docker/CLI delivery.

Spec Kit fits in as governance: before changing the router, we need to be able to answer "which requirement is being met, which test proves this, and which scoring decision justifies the change?".

## Principles To Adopt

### 1. Specification First

Every relevant competitive change must stem from a short specification:

- problem;
- official rule impacted;
- strategic decision;
- expected behavior;
- acceptance criteria;
- test or evidence.

### 2. Constitution Before Code

The project needs an operational constitution. For this Track 1:

- scoring governs;
- Fireworks tokens are a scarce resource;
- accuracy below the gate invalidates savings;
- auxiliary models cannot produce the final response;
- every routing behavior must be auditable;
- nothing depends on credits to evolve offline;
- secrets never appear in logs, READMEs, fixtures, or CI.

### 3. Plan Then Tasks

Each competitive feature must have:

- `spec.md`: what and why;
- `plan.md`: how it will be implemented;
- `tasks.md`: executable checklist;
- linked tests;
- updated documentation.

### 4. Test-First Where It Matters

For routing logic, we first define the behavior in a test:

- cheap task chooses a sufficiently cheap model;
- strong task does not choose an underqualified model;
- embedding/reranker never beats chat;
- expensive model only wins if there is a justifiable strategic gain;
- metadata explains the decision.

### 5. Converge After Implementation

After implementation, we run convergence:

- does the specification still describe the code?
- do tests cover the promised behavior?
- do docs explain the decision?
- does the runbook allow reproduction?
- does the change improve scoring or reduce risk?

## Proposed Flow Without Installing Anything Yet

Until we decide to install the official CLI, we adopt the manual structure:

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

This flow preserves mental compatibility with Spec Kit without introducing new dependencies.

## Proposed Flow With Spec Kit

If we decide to install:

```bash
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@vX.Y.Z
specify init . --integration codex
```

Before that, we need to validate:

- whether the `codex` integration is available in the installed version;
- whether the command does not overwrite existing files;
- which files would be created in `.specify/`, `specs/`, or agent directories;
- whether the project should use slash commands, skills mode, or just templates.

Conceptual commands of the Spec Kit:

- `constitution`: creates principles;
- `specify`: creates feature specification;
- `plan`: translates spec into a technical plan;
- `tasks`: generates executable tasks;
- `analyze`: verifies consistency between artifacts;
- `implement`: executes tasks according to the plan.

## How This Improves Our Pareto

Without Spec-Driven Development, every heuristic can become just an opinion.

With Spec-Driven Development, every heuristic needs to track:

- source: official rule, model card, benchmark, smoke test, or offline eval;
- decision: why that model enters or leaves;
- test: how to prove that the decision did not regress;
- metric: token, cost, latency, accuracy, mechanical pass/fail;
- risk: where the heuristic can break.

Example:

```text
Spec: choose the smallest sufficient Fireworks model.
Plan: calculate Pareto + Nash welfare by domain.
Tasks: implement matrix, metadata, tests, and docs.
Tests: gpt-oss-20b wins cheap; MiniMax M3 wins code when Kimi has marginal gain smaller than cost; embedding does not win chat.
```

## Adoption Rule

Do not install Spec Kit as a dependency of the main project yet.

First safe step:

- create Sprint 39;
- create manual constitution;
- apply the flow to a real feature;
- then decide if it is worth running `specify init`.

## Sources

- GitHub Spec Kit repository: https://github.com/github/spec-kit
- Spec-Driven Development guide: https://raw.githubusercontent.com/github/spec-kit/main/spec-driven.md
- Spec Kit documentation: https://github.github.io/spec-kit/
