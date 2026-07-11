# Sprint 39 - Spec-Driven Governance

## Type

Does not depend on credit.

## Objective

Adopt the best of `github/spec-kit` without installing or coupling the tool yet: specification as the source of truth, traceable technical plan, derived tasks, and convergence between docs, tests, and code.

## Thesis

Track 1 is a decision problem under constraints. If the specification does not govern the code, every routing heuristic becomes an opinion. If the specification governs, every change needs to prove its relationship with scoring, token budget, and accuracy.

## Deliverables

- Spec Kit adoption document.
- Operational constitution of the project.
- Initial `specs/` structure.
- First retroactive spec for the Fireworks Pareto Router.
- First retroactive spec for Game Theory Model Selection.
- Convergence checklist spec -> plan -> tasks -> tests.
- Documented decision on whether or not to install `specify-cli`.

## Checklist

- [x] Map `github/spec-kit` and relevant concepts.
- [x] Create `docs/SPEC_KIT_ADOPTION.md`.
- [ ] Create `specs/000-constitution/constitution.md`.
- [ ] Create `specs/001-fireworks-pareto-router/spec.md`.
- [ ] Create `specs/001-fireworks-pareto-router/plan.md`.
- [ ] Create `specs/001-fireworks-pareto-router/tasks.md`.
- [ ] Create `specs/002-game-theory-selection/spec.md`.
- [ ] Create `specs/002-game-theory-selection/plan.md`.
- [ ] Create `specs/002-game-theory-selection/tasks.md`.
- [ ] Add convergence checklist in `docs/SPEC_CONVERGENCE_CHECKLIST.md`.
- [ ] Decide whether it is worth installing `specify-cli` after reviewing dry-run/generated files.

## Initial Constitution

Non-negotiable principles:

- The official scoring governs.
- Accuracy below the gate invalidates token savings.
- Fireworks tokens are a scarce resource.
- Every model decision must be auditable.
- `ALLOWED_MODELS` governs the official path.
- Embedding and reranker do not produce a final response.
- The offline route cannot depend on credit.
- Tests must cover all competitive rules.
- Logs must never expose secrets or unnecessary sensitive payloads.
- The project remains CLI-first and Docker-ready.

## Definition of Done

- A project constitution exists.
- At least two core features have spec, plan, and tasks.
- The router can be explained from the specification, not just from the code.
- `scripts/offline_release_check.sh` continues to pass.
- The decision on whether or not to install Spec Kit is documented.

## Anti-Scope

- Do not install `specify-cli` directly in the repo without an explicit decision.
- Do not overwrite existing structure with automatic templates.
- Do not create bureaucracy that delays delivery.
- Do not turn specs into dead docs without linked tests.
