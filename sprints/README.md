# Sprints

Indice operacional do `Track 1 Token Router CLI`.

## Estado atual

As Sprints 01-05 ja entregaram a base executavel:

- CLI e contratos;
- M1 local;
- cascata local M1 -> M2A -> M2B;
- auditor Fireworks em modo hibrido;
- Docker, CI, README e submissao.

## Regra nova

A rota principal nao pode depender de credito AMD ou Fireworks.

Enquanto os creditos nao forem liberados, seguimos na trilha `offline`, usando datasets, simuladores, fake providers, eval harness e politicas de roteamento. Quando os creditos chegarem, a trilha `credit-gated` entra como acelerador, nao como bloqueio.

## Sprints concluidas

- [Sprint 01 - Fundacao e contratos](./01-foundation/README.md)
- [Sprint 02 - Modelo local e M1](./02-local-m1/README.md)
- [Sprint 03 - Verificador M2A e M2B](./03-local-verifier/README.md)
- [Sprint 04 - Fireworks e scoring](./04-fireworks-scoring/README.md)
- [Sprint 05 - Hardening e entrega](./05-hardening-submission/README.md)

## Proximas sprints sem credito

Estas sprints podem continuar imediatamente, sem AMD Developer Cloud e sem Fireworks real.

- [Sprint 06 - Offline Evaluation Arena](./06-offline-eval-arena/README.md)
- [Sprint 07 - Routing Policy Lab](./07-routing-policy-lab/README.md)
- [Sprint 08 - Fake Provider Chaos Lab](./08-fake-provider-chaos-lab/README.md)
- [Sprint 09 - Official Adapter Readiness](./09-official-adapter-readiness/README.md)
- [Sprint 10 - Offline Release Candidate](./10-offline-release-candidate/README.md)
- [Sprint 11 - Testing Culture Lab](./11-testing-culture-lab/README.md)

## Sprints dependentes de credito

Estas sprints so devem comecar quando houver acesso real a AMD Developer Cloud e/ou Fireworks.

- [Credit Sprint A - AMD Runtime Bring-up](./credit-a-amd-runtime-bringup/README.md)
- [Credit Sprint B - Fireworks Real Audit Calibration](./credit-b-fireworks-real-calibration/README.md)
- [Credit Sprint C - End-to-End Cost Benchmark](./credit-c-e2e-cost-benchmark/README.md)
- [Credit Sprint D - Final Cloud Submission Drill](./credit-d-final-cloud-drill/README.md)

## Regra de ouro

Cada sprint precisa terminar com:

- um comando rodando;
- um artefato testavel;
- uma metrica nova;
- uma decisao documentada;
- uma lista curta do que ficou para depois.

## Anti-escopo

Evitar nas proximas sprints:

- esperar credito para fazer trabalho offline;
- depender de notebook manual;
- calibrar prompt sem dataset;
- adicionar UI antes de melhorar scoring;
- trocar arquitetura sem ablation;
- publicar segredo em log, README, env ou CI;
- misturar debug com `stdout`.
