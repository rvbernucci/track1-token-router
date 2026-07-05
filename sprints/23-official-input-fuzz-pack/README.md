# Sprint 23 - Official Input Fuzz Pack

## Tipo

Nao depende de credito.

## Objetivo

Criar um pacote de fuzzing para simular formatos de input/output que podem aparecer no evaluator oficial, incluindo texto livre, JSON, JSONL, arquivos, payloads grandes, unicode, schemas rigidos e casos quebrados.

## Por que importa

O maior risco do kickoff nao e so modelo. E contrato. Se o input oficial vier diferente do que esperamos, o runner precisa falhar de forma controlada ou adaptar rapidamente.

## Entregaveis

- `evals/fuzz/tasks.jsonl`.
- `evals/fuzz/expected.jsonl`.
- Fixtures de arquivos anexos.
- Script `scripts/generate_fuzz_eval.py`.
- Script `scripts/run_fuzz_eval.py`.
- Relatorio `reports/generated/fuzz-report.md`.
- Testes de adapters e CLI contra payloads adversariais.

## Checklist

- [ ] Criar casos de texto vazio.
- [ ] Criar casos com whitespace extremo.
- [ ] Criar casos com unicode e acentos.
- [ ] Criar casos multi-linha.
- [ ] Criar casos JSON com campos alternativos.
- [ ] Criar casos JSONL com linhas invalidas controladas.
- [ ] Criar casos com arquivo `.txt`.
- [ ] Criar casos com arquivo `.json`.
- [ ] Criar casos com payload grande.
- [ ] Criar casos de resposta `number only`.
- [ ] Criar casos de resposta JSON compacta.
- [ ] Criar casos de literal echo.
- [ ] Criar casos com markdown proibido.
- [ ] Validar que erros controlados vao para `stderr`.
- [ ] Validar que `stdout` nao recebe debug.
- [ ] Integrar fuzz report ao battle drill.

## Criterios de aceite

- O pacote roda sem creditos.
- O runner nao quebra com formatos estranhos.
- O relatorio mostra classes de input e taxa de sucesso.
- Falhas de parse sao controladas e testadas.

## Saida esperada

Menos surpresa no kickoff e maior chance de adaptar o adapter oficial em minutos, nao horas.

## Decisao

O fuzz pack deve testar contrato e robustez, nao qualidade semantica profunda. Ele existe para proteger o runner contra formato inesperado.

