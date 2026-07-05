# Sprint 11 - Testing Culture Lab

## Tipo

Nao depende de credito.

## Objetivo

Criar uma cultura explicita de testes para que toda logica importante tenha um lugar claro para ser experimentada, validada e protegida contra regressao.

Em TypeScript, muitas vezes usamos um `test.ts` rapido para testar uma ideia. Em Python, vamos separar isso em tres camadas:

- `playground/`: experimentos manuais e descartaveis.
- `tests/`: garantias automatizadas que rodam no CI.
- `fixtures/`: exemplos estaveis usados por testes e adapters.

## Entregaveis

- Guia `docs/TESTING_CULTURE.md`.
- Pasta `playground/` com exemplos executaveis.
- Matriz de cobertura por area critica.
- Script para listar testes por dominio.
- Regra de promocao: playground -> teste automatizado.
- Checklists para novas logicas.
- CI garantindo que os exemplos principais nao apodrecem.

## Checklist

- [ ] Criar `docs/TESTING_CULTURE.md`.
- [ ] Criar `playground/README.md`.
- [ ] Criar `playground/test_policy_logic.py`.
- [ ] Criar `playground/test_adapter_logic.py`.
- [ ] Criar `playground/test_prompt_packets.py`.
- [ ] Criar `docs/TEST_MATRIX.md`.
- [ ] Mapear areas: contracts, adapters, policies, prompts, cascade, fake provider, evals, CLI.
- [ ] Criar `scripts/list_test_coverage.py`.
- [ ] Adicionar teste que valida a matriz de testes.
- [ ] Documentar quando usar `playground` versus `tests`.
- [ ] Adicionar comando no README.

## Criterios de aceite

- Existe uma forma rapida de testar logica manualmente, equivalente ao espirito de um `test.ts`.
- Toda logica critica tem pelo menos um teste automatizado mapeado.
- A matriz deixa claro o que esta coberto e o que falta cobrir.
- `scripts/offline_release_check.sh` continua passando.
- Nenhum playground depende de credito real.

## Regra de promocao

Um arquivo em `playground/` deve virar teste em `tests/` quando:

- capturar um bug real;
- validar comportamento competitivo;
- proteger contrato de input/output;
- envolver scoring, token usage ou roteamento;
- for usado mais de uma vez.

## Anti-escopo

- Nao perseguir 100% coverage numerico sem criterio.
- Nao criar testes fragilmente acoplados a texto exato de prompt quando o contrato nao exige isso.
- Nao depender de modelos reais.
- Nao transformar playground em segunda suite paralela obrigatoria.

## Saida esperada

Uma cultura de testes clara: experimentar rapido, promover o que importa, e manter o CI protegendo a logica competitiva.
