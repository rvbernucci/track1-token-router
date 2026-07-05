# Sprints

Indice operacional dos 5 sprints do `Track 1 Token Router CLI`.

## Sequencia

- [Sprint 01 - Fundacao e contratos](./01-foundation/README.md)
- [Sprint 02 - Modelo local e M1](./02-local-m1/README.md)
- [Sprint 03 - Verificador M2A e M2B](./03-local-verifier/README.md)
- [Sprint 04 - Fireworks e scoring](./04-fireworks-scoring/README.md)
- [Sprint 05 - Hardening e entrega](./05-hardening-submission/README.md)

## Regra de ouro

Cada sprint precisa terminar com:

- um comando rodando;
- um artefato testavel;
- uma metrica nova;
- uma decisao documentada;
- uma lista curta do que ficou para depois.

## Anti-escopo

Evitar durante as cinco sprints:

- UI web antes do runner estar competitivo;
- banco vetorial antes de existir necessidade real;
- Neo4j ou grafo sem scoring que justifique;
- prompt gigantesco sem teste A/B;
- classificadores complexos antes de medir a cascata simples;
- dependencia manual de notebooks;
- logs misturados no `stdout`.

